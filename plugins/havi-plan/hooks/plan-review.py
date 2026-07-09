#!/usr/bin/env python3
"""PreToolUse hook for ExitPlanMode: serve the plan for human review in the browser.

Claude Code runs this before an ExitPlanMode tool call. It serves the submitted
plan as a local web page, opens the browser, and blocks until the reviewer picks
Approve or Request changes (or an internal deadline elapses).

Approve  -> permissionDecision "allow" (echoing updatedInput, required for
            ExitPlanMode) and zero HAVI/MCP calls.
Request changes / deadline / any error -> permissionDecision "deny" with a
            machine-readable marker so the agent can fetch this review's HAVI
            annotations and revise.

Python 3 standard library only. Exactly one JSON object is written to stdout on
every path; exit status is always 0.
"""

import html as html_lib
import json
import os
import re
import shlex
import subprocess
import sys
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DEFAULT_DEADLINE_SECONDS = 3540.0


# --------------------------------------------------------------------------- #
# Hook output helpers
# --------------------------------------------------------------------------- #
def allow_output(tool_input, reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
            "updatedInput": tool_input,
        }
    }


def deny_output(reason):
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def emit(output):
    sys.stdout.write(json.dumps(output))
    sys.stdout.flush()


# --------------------------------------------------------------------------- #
# Deny reason marker (fed back to the model)
# --------------------------------------------------------------------------- #
_CHANGES_TAIL = (
    "Reviewer requested changes. Fetch this plan's open annotations via the havi "
    'MCP tool list_annotations with {{worktree:"{pid}", state:"open"}} (if empty, '
    "retry once after ~5s -- sync delay). Read each annotation's body[] entry with "
    'purpose "commenting"; use get_annotation_image(id) when the screenshot helps. '
    "Revise the plan to address every comment, then re-submit via ExitPlanMode. "
    'Optionally resolve_annotation({{ids:[...], resolution:{{note:"addressed in '
    'revised plan"}}}}) for addressed notes.'
)

_TIMEOUT_TAIL = (
    "No review within the time limit -- plan not approved. The plan was not "
    "reviewed before the window closed. Re-submit the plan via ExitPlanMode to "
    "request review again. If the reviewer did leave notes, fetch them via the "
    'havi MCP tool list_annotations with {{worktree:"{pid}", state:"open"}} and '
    "address them first."
)


def deny_reason(plan_id, domain, tail):
    marker = "HAVI_PLAN_REVIEW_ID={pid} HAVI_DOMAIN={domain} -- ".format(
        pid=plan_id, domain=domain
    )
    return marker + tail.format(pid=plan_id)


# --------------------------------------------------------------------------- #
# Minimal, safe Markdown -> HTML converter (no raw HTML passthrough)
# --------------------------------------------------------------------------- #
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_EM_STAR_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
_EM_UNDER_RE = re.compile(r"(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
_OL_RE = re.compile(r"^\s*\d+\.\s+(.*)$")
_FENCE_RE = re.compile(r"^\s*```")


def _safe_href(url):
    low = url.lower()
    if low.startswith(("http://", "https://", "mailto:")) or url.startswith(("/", "#")):
        return url
    return None


def _render_inline(text):
    """Inline formatting on already HTML-escaped text."""
    codes = []

    def _stash(match):
        codes.append("<code>" + match.group(1) + "</code>")
        return "\x00C%d\x00" % (len(codes) - 1)

    text = _INLINE_CODE_RE.sub(_stash, text)

    def _link(match):
        label, url = match.group(1), match.group(2)
        href = _safe_href(url)
        if href is None:
            return label
        return (
            '<a href="' + href + '" target="_blank" rel="noopener noreferrer">'
            + label + "</a>"
        )

    text = _LINK_RE.sub(_link, text)
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = _EM_STAR_RE.sub(r"<em>\1</em>", text)
    text = _EM_UNDER_RE.sub(r"<em>\1</em>", text)

    for index, code in enumerate(codes):
        text = text.replace("\x00C%d\x00" % index, code)
    return text


def _inline(raw):
    return _render_inline(html_lib.escape(raw.strip()))


def markdown_to_html(md):
    lines = md.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out = []
    para = []
    i = 0
    n = len(lines)

    def flush_para():
        if para:
            out.append("<p>" + _inline(" ".join(l.strip() for l in para)) + "</p>")
            para.clear()

    while i < n:
        line = lines[i]

        if _FENCE_RE.match(line):
            flush_para()
            i += 1
            code_lines = []
            while i < n and not _FENCE_RE.match(lines[i]):
                code_lines.append(lines[i])
                i += 1
            i += 1  # consume closing fence (or step past end)
            escaped = html_lib.escape("\n".join(code_lines))
            out.append("<pre><code>" + escaped + "</code></pre>")
            continue

        if line.strip() == "":
            flush_para()
            i += 1
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            flush_para()
            level = len(heading.group(1))
            out.append("<h%d>%s</h%d>" % (level, _inline(heading.group(2)), level))
            i += 1
            continue

        if _UL_RE.match(line):
            flush_para()
            items = []
            while i < n and _UL_RE.match(lines[i]):
                items.append(_UL_RE.match(lines[i]).group(1))
                i += 1
            out.append(
                "<ul>" + "".join("<li>" + _inline(it) + "</li>" for it in items) + "</ul>"
            )
            continue

        if _OL_RE.match(line):
            flush_para()
            items = []
            while i < n and _OL_RE.match(lines[i]):
                items.append(_OL_RE.match(lines[i]).group(1))
                i += 1
            out.append(
                "<ol>" + "".join("<li>" + _inline(it) + "</li>" for it in items) + "</ol>"
            )
            continue

        para.append(line)
        i += 1

    flush_para()
    if not out:
        return '<p class="empty">No plan content was provided.</p>'
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Review page
# --------------------------------------------------------------------------- #
PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<script>window.__HAVI_DEV__ = {project:"plan-review", worktree:"__PLAN_ID__", branch:"__PLAN_ID__"};</script>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HAVI Plan Review</title>
<style>
:root {
  --bg: #f7f7f5;
  --panel: #ffffff;
  --ink: #1a1a19;
  --muted: #6b6b66;
  --border: #e4e4e0;
  --code-bg: #f0f0ec;
  --accent: #0f766e;
  --accent-ink: #ffffff;
  --accent-hover: #0c5f58;
  --shadow: 0 1px 2px rgba(0,0,0,.04), 0 12px 32px rgba(0,0,0,.06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #16161a;
    --panel: #1e1e24;
    --ink: #ececed;
    --muted: #9a9aa2;
    --border: #2c2c34;
    --code-bg: #26262e;
    --accent: #2dd4bf;
    --accent-ink: #08211d;
    --accent-hover: #45e0cd;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 16px 40px rgba(0,0,0,.4);
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  background: var(--bg);
  color: var(--ink);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.6;
  -webkit-font-smoothing: antialiased;
}
main {
  max-width: 760px;
  margin: 0 auto;
  padding: 48px 24px 140px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  letter-spacing: .12em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
  margin-bottom: 6px;
}
.brand .dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--accent);
}
h1.title {
  font-size: 26px;
  line-height: 1.25;
  margin: 0 0 28px;
  font-weight: 650;
  letter-spacing: -.01em;
}
.plan {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 28px 32px;
  box-shadow: var(--shadow);
}
.plan > :first-child { margin-top: 0; }
.plan > :last-child { margin-bottom: 0; }
.plan h1, .plan h2, .plan h3, .plan h4, .plan h5, .plan h6 {
  line-height: 1.3;
  margin: 1.5em 0 .5em;
  font-weight: 640;
  letter-spacing: -.01em;
}
.plan h1 { font-size: 22px; }
.plan h2 { font-size: 19px; }
.plan h3 { font-size: 17px; }
.plan h4, .plan h5, .plan h6 { font-size: 15px; }
.plan p { margin: 0 0 1em; }
.plan ul, .plan ol { margin: 0 0 1em; padding-left: 1.4em; }
.plan li { margin: .25em 0; }
.plan a { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }
.plan code {
  background: var(--code-bg);
  border-radius: 5px;
  padding: .12em .4em;
  font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
  font-size: .88em;
}
.plan pre {
  background: var(--code-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 18px;
  overflow-x: auto;
  margin: 0 0 1em;
}
.plan pre code { background: none; padding: 0; font-size: .86em; line-height: 1.5; }
.plan .empty { color: var(--muted); font-style: italic; }
.actionbar {
  position: fixed;
  left: 0; right: 0; bottom: 0;
  background: color-mix(in srgb, var(--bg) 82%, transparent);
  backdrop-filter: saturate(1.4) blur(10px);
  border-top: 1px solid var(--border);
  padding: 16px 24px;
}
.actionbar-inner {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}
.hint { color: var(--muted); font-size: 13.5px; margin: 0; flex: 1 1 220px; }
.buttons { display: flex; gap: 12px; }
.btn {
  font: inherit;
  font-weight: 600;
  font-size: 14.5px;
  border-radius: 10px;
  padding: 11px 20px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: transform .12s ease, background .15s ease, border-color .15s ease, box-shadow .15s ease, opacity .15s ease;
}
.btn:active { transform: translateY(1px); }
.btn-primary {
  background: var(--accent);
  color: var(--accent-ink);
  box-shadow: 0 1px 2px rgba(0,0,0,.12);
}
.btn-primary:hover { background: var(--accent-hover); box-shadow: 0 4px 14px rgba(15,118,110,.28); }
.btn-secondary {
  background: transparent;
  color: var(--ink);
  border-color: var(--border);
}
.btn-secondary:hover { border-color: var(--muted); background: color-mix(in srgb, var(--ink) 6%, transparent); }
.btn:disabled { opacity: .5; cursor: default; transform: none; box-shadow: none; }
.done {
  max-width: 760px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--muted);
  font-size: 14.5px;
  font-weight: 500;
}
.done .check { color: var(--accent); font-weight: 700; }
</style>
</head>
<body>
<main>
  <div class="brand"><span class="dot"></span> HAVI Plan Review</div>
  <h1 class="title">Review this plan before Claude proceeds</h1>
  <article class="plan">
__PLAN_HTML__
  </article>
</main>
<div class="actionbar">
  <div class="actionbar-inner" id="actions">
    <p class="hint">Mark up the plan with HAVI annotations, then choose.</p>
    <div class="buttons">
      <button id="changes" class="btn btn-secondary" type="button">Request changes</button>
      <button id="approve" class="btn btn-primary" type="button">Approve</button>
    </div>
  </div>
  <div class="actionbar-inner done" id="done" hidden>
    <span class="check">&#10003;</span> Thanks &mdash; back to Claude. You can close this tab.
  </div>
</div>
<script>
(function () {
  var done = false;
  function choose(decision) {
    if (done) return;
    done = true;
    var approve = document.getElementById("approve");
    var changes = document.getElementById("changes");
    approve.disabled = true;
    changes.disabled = true;
    function finish() {
      document.getElementById("actions").hidden = true;
      document.getElementById("done").hidden = false;
      setTimeout(function () { try { window.close(); } catch (e) {} }, 500);
    }
    fetch("/decision", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision: decision })
    }).catch(function () {}).then(finish);
  }
  document.getElementById("approve").addEventListener("click", function () { choose("approve"); });
  document.getElementById("changes").addEventListener("click", function () { choose("request_changes"); });
})();
</script>
</body>
</html>
"""


def build_page(plan_id, plan_markdown):
    plan_html = markdown_to_html(plan_markdown or "")
    return PAGE_TEMPLATE.replace("__PLAN_ID__", plan_id).replace(
        "__PLAN_HTML__", plan_html
    )


# --------------------------------------------------------------------------- #
# HTTP server
# --------------------------------------------------------------------------- #
class ReviewHandler(BaseHTTPRequestHandler):
    def _send(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path in ("/", ""):
            self._send(200, "text/html; charset=utf-8", self.server.page_html.encode("utf-8"))
        elif path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self._send(404, "text/plain; charset=utf-8", b"not found")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/decision":
            self._send(404, "text/plain; charset=utf-8", b"not found")
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        raw = self.rfile.read(length) if length else b""
        decision = None
        try:
            decision = (json.loads(raw.decode("utf-8")) or {}).get("decision")
        except (ValueError, UnicodeDecodeError):
            decision = None

        accepted = False
        if decision in ("approve", "request_changes") and not self.server.decision_event.is_set():
            self.server.decision_result["decision"] = decision
            self.server.decision_event.set()
            accepted = True

        self._send(
            200,
            "application/json",
            json.dumps({"ok": True, "accepted": accepted}).encode("utf-8"),
        )

    def log_message(self, *args):  # silence default stderr request logging
        return


# --------------------------------------------------------------------------- #
# Browser launch
# --------------------------------------------------------------------------- #
def open_browser(url):
    override = os.environ.get("PLAN_REVIEW_BROWSER", "").strip()
    if override:
        cmd = shlex.split(override) + [url]
    elif sys.platform == "darwin":
        cmd = ["open", url]
    else:
        cmd = ["xdg-open", url]
    try:
        subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        # A dead launcher must not crash the hook; the deadline deny covers it.
        pass


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def get_deadline():
    raw = os.environ.get("PLAN_REVIEW_DEADLINE", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_DEADLINE_SECONDS


def read_input():
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}
    plan = tool_input.get("plan")
    if not isinstance(plan, str):
        plan = ""
    return tool_input, plan


# --------------------------------------------------------------------------- #
# Main flow
# --------------------------------------------------------------------------- #
def main():
    tool_input, plan = read_input()

    if os.environ.get("PLAN_REVIEW_NO_BROWSER", "").strip() == "1":
        return allow_output(
            tool_input,
            "PLAN_REVIEW_NO_BROWSER=1 -- headless mode, plan approved without human review.",
        )

    plan_id = uuid.uuid4().hex
    server = ThreadingHTTPServer(("127.0.0.1", 0), ReviewHandler)
    port = server.server_address[1]
    domain = "127.0.0.1:%d" % port

    server.page_html = build_page(plan_id, plan)
    server.decision_event = threading.Event()
    server.decision_result = {"decision": None}

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        open_browser("http://%s/" % domain)
        signaled = server.decision_event.wait(timeout=get_deadline())
    finally:
        server.shutdown()
        server.server_close()

    if signaled and server.decision_result["decision"] == "approve":
        return allow_output(tool_input, "Reviewer approved the plan in the browser.")
    if signaled and server.decision_result["decision"] == "request_changes":
        return deny_output(deny_reason(plan_id, domain, _CHANGES_TAIL))
    return deny_output(deny_reason(plan_id, domain, _TIMEOUT_TAIL))


if __name__ == "__main__":
    try:
        output = main()
    except Exception as exc:  # never crash; never silently approve
        output = deny_output(
            "HAVI plan review could not run (%s). Plan not approved; "
            "re-submit via ExitPlanMode to try again." % exc
        )
    emit(output)
    sys.exit(0)
