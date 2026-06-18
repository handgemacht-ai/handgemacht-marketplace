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

Once connected, the server provides slash-command prompts (`review`, `triage`,
`resolve`) that walk the agent through annotation review for the current repo.

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

## Package rules

The public package must stay safe to publish:

- no private `handgemacht-ai/havi` source URLs as install sources
- no raw auth tokens
- no internal credentials
- no Handgemacht-only setup instructions
