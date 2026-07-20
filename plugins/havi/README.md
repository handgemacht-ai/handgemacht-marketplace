# HAVI Plugin Package

This package is shared by the public Claude Code and Codex marketplaces.

## Claude Code

Install the plugin, then log in with `/mcp`:

```
/plugin marketplace add handgemacht-ai/handgemacht-marketplace
/plugin install havi@handgemacht
/mcp
```

The plugin bundles the hosted HAVI MCP server (`./.mcp.json`), so `/mcp` lists
`havi` directly. Select **havi → Authenticate** and confirm in the browser. No
setup code, no token to paste, and no local server.

## Codex

Codex has no in-app OAuth login, so it still uses a one-time setup code from the
HAVI `/try` connect page:

```
codex plugin marketplace add handgemacht-ai/handgemacht-marketplace
codex plugin add havi@handgemacht
codex havi-setup <hosted-mcp-url> <setup-code>
```

For example:

```
codex havi-setup https://havi.handgemacht.ai/api/mcp ABC123
```

`havi-setup` exchanges the short-lived setup code for a bearer token and writes
the hosted `/api/mcp` server into your MCP config — no local server, no binary to
install. The setup code expires quickly; generate a fresh one on the `/try`
connect page each time. Never paste a raw bearer token into the command; always
use a setup code from the dashboard.

## Prompts

Once connected, the server provides four slash-command prompts. Both clients talk
to the same hosted server, so the same four are available in each. Each prompt
returns instructions the agent runs through the MCP tools — the server emits
text, the agent does the work.

### `review`: read your worktree before you fix

Reviews the open visual annotations for your own git worktree or branch. It
detects your git context, scopes to your own worktree so parallel sessions stay
isolated, lists the open annotations for that scope, pulls any screenshots, and
proposes a concrete fix for each one citing file and line. It stops before
resolving: you see the plan first and confirm per item.

- `worktree` (optional) — the git worktree to scope to. Takes precedence over `branch`.
- `branch` (optional) — fallback filter, used when you are not in a linked worktree.
- Omit both and the agent detects its own branch, worktree, and repo, then prefers the worktree filter. It omits the filter entirely when detection is empty, because an empty value would match every other session's untagged annotations.

### `triage`: one prioritized summary of everything open

Lists every open annotation in the workspace, groups the results by domain and by
motivation, and returns a prioritized summary of what to fix first and why. It is
read-only — it fixes and resolves nothing. Unlike `review`, it is not scoped to a
worktree or branch; it covers the whole workspace. Takes no arguments.

### `resolve`: fix one annotation and close it

Recalls what a single annotation was about, makes the described fix in the
codebase, captures the current commit with `git rev-parse --short HEAD`, and
calls the `resolve_annotation` tool with the id, a note, and that commit. Unlike
`triage` and `review`, this one changes code.

- `id` (required) — the annotation to resolve. Without it the prompt returns an error.
- `note` (optional) — a short note describing the fix, dropped verbatim into the resolution. Omit it and the agent writes its own.

### `setup_hooks`: attach project context to every capture

Wires build- or boot-time context into the page so each annotation carries it.
HAVI reads a global set at boot:

```js
window.__HAVI_DEV__ = { project, worktree, branch, commit, port }
```

The `window.Havi` SDK bundled into the widget and the browser extension reads
that global at capture time and attaches it to every annotation; apps can also
call `Havi.setDev({...})` for runtime-only values. The prompt asks whether you
want custom fields, emits the matching framework template, and reminds you to
restart the dev server after switching branches — `branch` and `commit` are read
at boot and stay stale until then.

- `framework` (optional) — one of `nextjs`, `vite`, or `phoenix` returns just that framework's template.
- Omit it and the agent detects the framework from config files (`next.config.*`, `vite.config.*`, `mix.exs` with `:phoenix`) and returns all three templates. Anything else falls back to setting `window.__HAVI_DEV__` by hand.

## Package rules

The public package must stay safe to publish:

- no private `handgemacht-ai/havi` source URLs as install sources
- no raw auth tokens
- no internal credentials
- no Handgemacht-only setup instructions
