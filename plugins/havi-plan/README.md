# havi-plan

Human plan review for Claude Code. When Claude Code finishes planning and calls
the built-in `ExitPlanMode` tool, this plugin pauses the agent, opens the plan in
your browser, and waits for you to decide.

- **Approve** &rarr; the plan is allowed and Claude proceeds. No HAVI or MCP
  calls happen at all.
- **Request changes** &rarr; the plan is denied and Claude is told to fetch this
  review's notes and revise. Mark the plan up with the HAVI Chrome extension
  first; the agent reads those annotations, addresses each one, and re-submits.
  The loop repeats until you approve.

The review page tags itself for HAVI so only *this* plan's annotations come back:
it sets a per-review id on `window.__HAVI_DEV__` and is served on a private
`127.0.0.1` port, so the agent's `list_annotations` query is scoped to the
current review only.

## Install

```
/plugin marketplace add handgemacht-ai/handgemacht-marketplace
/plugin install havi-plan@handgemacht
```

Claude Code picks up the hook automatically after install. Nothing else to run.

## Requirements

- An **interactive** Claude Code session (plan review is skipped in headless /
  `claude -p` runs, where `ExitPlanMode` does not exist anyway).
- **Python 3** available as `python3` on the PATH.
- To mark plans up, the **HAVI Chrome extension** installed in your default
  browser and signed in.
- To act on requested changes, the separate **`havi` plugin** installed and
  authenticated (`/plugin install havi@handgemacht`, then `/mcp`), so the agent
  can fetch annotations via `list_annotations` / `get_annotation_image` /
  `resolve_annotation`.

## How it works

1. The hook receives the plan (markdown) on stdin.
2. It starts a tiny local web server on a random `127.0.0.1` port and renders the
   plan as a clean, self-contained page (light/dark, no external requests).
3. It opens your browser and blocks.
4. You optionally annotate the page with the HAVI extension, then click
   **Approve** or **Request changes**.
5. The hook returns the decision to Claude Code.

On **Request changes** the decision reason starts with a machine-readable marker,
for example:

```
HAVI_PLAN_REVIEW_ID=<id> HAVI_DOMAIN=127.0.0.1:<port> -- Reviewer requested changes. ...
```

Claude uses the `<id>` to fetch exactly this review's open annotations.

## Configuration

All optional, via environment variables:

| Variable | Default | Effect |
|---|---|---|
| `PLAN_REVIEW_DEADLINE` | `3540` | Seconds to wait for a decision before giving up. Kept below the hook timeout so review never silently auto-approves. |
| `PLAN_REVIEW_NO_BROWSER` | unset | Set to `1` to skip review entirely and approve immediately (headless / CI safety). |
| `PLAN_REVIEW_BROWSER` | unset | Command used to open the page; the URL is passed as its single argument. Overrides the default `open` (macOS) / `xdg-open` (Linux). |

## Edge cases

- **Comments left but Approve clicked** &rarr; the comments are ignored by design.
  Approve means proceed; the plugin makes no HAVI calls on approval.
- **Timeout** &rarr; the review window closing counts as **deny**, never approve.
  If the harness-level hook timeout ever fires first, Claude Code treats the tool
  as approved, so the plugin keeps its own deadline strictly below that timeout.
- **No `python3`** &rarr; the hook cannot run; install Python 3 or the plan step
  will fail.
- **Browser fails to open** &rarr; the hook keeps waiting; open the printed
  `http://127.0.0.1:<port>/` URL manually, or let the deadline deny the plan.
