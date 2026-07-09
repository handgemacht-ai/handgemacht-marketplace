#!/usr/bin/env python3
"""Tests for the havi-plan ExitPlanMode review hook.

Each test drives hooks/plan-review.py as a subprocess, exactly how Claude Code
runs it. The random review port is discovered via PLAN_REVIEW_BROWSER: a helper
that writes the URL it is handed to a file the test reads.
"""

import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.parse
import urllib.request

HOOK = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "hooks",
    "plan-review.py",
)


class PlanReviewHookTest(unittest.TestCase):
    def _browser_helper(self, tmpdir):
        helper = os.path.join(tmpdir, "browser_helper.py")
        with open(helper, "w") as fh:
            fh.write(
                "import os, sys\n"
                "with open(os.environ['HAVI_TEST_URL_FILE'], 'w') as f:\n"
                "    f.write(sys.argv[1] if len(sys.argv) > 1 else '')\n"
            )
        return helper

    def _env(self, **extra):
        env = dict(os.environ)
        env.pop("PLAN_REVIEW_NO_BROWSER", None)
        env.pop("PLAN_REVIEW_DEADLINE", None)
        env.pop("PLAN_REVIEW_BROWSER", None)
        env.update({k: v for k, v in extra.items() if v is not None})
        return env

    def _browser_cmd(self, helper):
        return shlex.quote(sys.executable) + " " + shlex.quote(helper)

    def _start(self, input_obj, env):
        stdin_file = tempfile.TemporaryFile(mode="w+")
        stdin_file.write(json.dumps(input_obj))
        stdin_file.flush()
        stdin_file.seek(0)
        proc = subprocess.Popen(
            [sys.executable, HOOK],
            stdin=stdin_file,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        stdin_file.close()
        return proc

    def _wait_for_url(self, urlfile, timeout=15):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if os.path.exists(urlfile):
                with open(urlfile) as fh:
                    data = fh.read().strip()
                if data:
                    return data
            time.sleep(0.05)
        raise AssertionError("browser helper never received a URL")

    def _get(self, url):
        return urllib.request.urlopen(url, timeout=10).read().decode("utf-8")

    def _post_decision(self, url, decision):
        req = urllib.request.Request(
            url.rstrip("/") + "/decision",
            data=json.dumps({"decision": decision}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urllib.request.urlopen(req, timeout=10).read()

    def _finish(self, proc):
        if proc.poll() is None:
            proc.kill()
            proc.communicate()

    # -- headless -------------------------------------------------------- #
    def test_headless_no_browser_allows_with_updated_input(self):
        tool_input = {"plan": "# Plan\n\n- step one\n- step two"}
        env = self._env(PLAN_REVIEW_NO_BROWSER="1")
        proc = self._start(
            {"tool_name": "ExitPlanMode", "tool_input": tool_input}, env
        )
        out, err = proc.communicate(timeout=15)
        result = json.loads(out)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["hookEventName"], "PreToolUse")
        self.assertEqual(hso["permissionDecision"], "allow", err)
        self.assertIn("updatedInput", hso)
        self.assertEqual(hso["updatedInput"], tool_input)

    # -- approve --------------------------------------------------------- #
    def test_approve_returns_allow_with_updated_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._browser_helper(tmp)
            urlfile = os.path.join(tmp, "url.txt")
            env = self._env(
                PLAN_REVIEW_BROWSER=self._browser_cmd(helper),
                HAVI_TEST_URL_FILE=urlfile,
                PLAN_REVIEW_DEADLINE="30",
            )
            tool_input = {"plan": "# Ship it\n\nDo the **thing** now with `care`."}
            proc = self._start(
                {"tool_name": "ExitPlanMode", "tool_input": tool_input}, env
            )
            try:
                url = self._wait_for_url(urlfile)
                page = self._get(url)
                match = re.search(r'worktree:"([0-9a-f]{32})"', page)
                self.assertIsNotNone(match, "PLAN_ID not found in __HAVI_DEV__")
                self.assertIn("Do the", page)
                self.assertIn("<strong>thing</strong>", page)
                self.assertIn("<code>care</code>", page)
                self._post_decision(url, "approve")
                out, err = proc.communicate(timeout=30)
            finally:
                self._finish(proc)
        result = json.loads(out)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "allow", err)
        self.assertEqual(hso["updatedInput"], tool_input)

    # -- request changes ------------------------------------------------- #
    def test_request_changes_returns_deny_with_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._browser_helper(tmp)
            urlfile = os.path.join(tmp, "url.txt")
            env = self._env(
                PLAN_REVIEW_BROWSER=self._browser_cmd(helper),
                HAVI_TEST_URL_FILE=urlfile,
                PLAN_REVIEW_DEADLINE="30",
            )
            proc = self._start(
                {
                    "tool_name": "ExitPlanMode",
                    "tool_input": {"plan": "Refactor the auth module."},
                },
                env,
            )
            try:
                url = self._wait_for_url(urlfile)
                page = self._get(url)
                plan_id = re.search(r'worktree:"([0-9a-f]{32})"', page).group(1)
                port = urllib.parse.urlparse(url).port
                self._post_decision(url, "request_changes")
                out, err = proc.communicate(timeout=30)
            finally:
                self._finish(proc)
        result = json.loads(out)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny", err)
        reason = hso["permissionDecisionReason"]
        self.assertIn("HAVI_PLAN_REVIEW_ID=" + plan_id, reason)
        self.assertIn("HAVI_DOMAIN=127.0.0.1:%d" % port, reason)
        self.assertIn("list_annotations", reason)

    # -- timeout --------------------------------------------------------- #
    def test_timeout_returns_deny(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = self._browser_helper(tmp)
            urlfile = os.path.join(tmp, "url.txt")
            env = self._env(
                PLAN_REVIEW_BROWSER=self._browser_cmd(helper),
                HAVI_TEST_URL_FILE=urlfile,
                PLAN_REVIEW_DEADLINE="1",
            )
            proc = self._start(
                {
                    "tool_name": "ExitPlanMode",
                    "tool_input": {"plan": "Anything at all."},
                },
                env,
            )
            out, err = proc.communicate(timeout=20)
        result = json.loads(out)
        hso = result["hookSpecificOutput"]
        self.assertEqual(hso["permissionDecision"], "deny", err)
        self.assertIn("HAVI_PLAN_REVIEW_ID=", hso["permissionDecisionReason"])

    # -- hooks.json shape ------------------------------------------------ #
    def test_hooks_json_shape(self):
        path = os.path.join(os.path.dirname(HOOK), "hooks.json")
        with open(path) as fh:
            cfg = json.load(fh)
        pre = cfg["hooks"]["PreToolUse"]
        self.assertEqual(len(pre), 1)
        entry = pre[0]
        self.assertEqual(entry["matcher"], "ExitPlanMode")
        hook = entry["hooks"][0]
        self.assertEqual(hook["type"], "command")
        self.assertIn("plan-review.py", hook["command"])
        self.assertIn("CLAUDE_PLUGIN_ROOT", hook["command"])
        self.assertEqual(hook["timeout"], 3600)


if __name__ == "__main__":
    unittest.main()
