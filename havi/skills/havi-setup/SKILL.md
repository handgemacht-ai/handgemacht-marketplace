---
name: havi-setup
description: Connect Claude Code to the HAVI hosted service using an MCP URL and setup code from the /try connect page.
allowed-tools: Bash
user-invocable: true
---

## HAVI Setup

This skill connects Claude Code to the HAVI hosted MCP server. It requires two arguments from the HAVI /try connect page:

- `mcp_url` — the HAVI MCP endpoint (e.g. `https://havi.ai/api/mcp`)
- `setup_code` — the short code shown on the connect page after the user approves the connection

### How it works

1. The user visits the HAVI /try page and approves the connection. This generates a one-time `setup_code`.
2. This skill calls `havi-setup <mcp_url> <setup_code>`.
3. The script POSTs `{"device_code": "<setup_code>"}` to `<origin>/api/setup/link/exchange`.
4. On success (HTTP 201) it receives `{"data": {"token": "...", "token_type": "Bearer", "workspace": {"id": "..."}, ...}}`.
5. The script calls `claude mcp add --transport http --header "Authorization: Bearer <token>" --header "x-havi-workspace-id: <workspace_id>" havi <mcp_url>` to register the MCP server.

### Run it

```bash
bash "${CLAUDE_PLUGIN_ROOT}/bin/havi-setup" <mcp_url> <setup_code>
```

Example:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/bin/havi-setup" https://havi.ai/api/mcp abc123xyz
```

### After it succeeds

Tell the user:

> HAVI is connected. Restart Claude Code so the MCP client picks up the new server:
> ```
> claude
> ```
> Then you can use HAVI annotation tools in your session.

### Error guidance

| Status | Meaning | Action |
|--------|---------|--------|
| 202 | Code not approved yet | Approve on the /try connect page, then re-run |
| 400 | Code missing or malformed | Check the setup_code argument |
| 404 | Code not found | Verify the code from the /try connect page |
| 409 | Code already used | Generate a new code on the /try connect page |
| 410 | Code expired | Generate a new code on the /try connect page |

Do not ask the user to paste a raw bearer token into chat. The setup code is short and safe to share in conversation. The token is never printed to stdout or stderr.
