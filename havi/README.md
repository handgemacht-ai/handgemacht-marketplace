# HAVI Plugin

Claude Code plugin for the HAVI hosted annotation service.

## Setup

Add the public marketplace, install the plugin, then run the setup command with
the credentials shown on the HAVI `/try` connect page:

```
/plugin marketplace add handgemacht-ai/handgemacht-marketplace
/plugin install havi@handgemacht-marketplace
/havi-setup <hosted-mcp-url> <setup-code>
```

For example:

```
/havi-setup https://havi.handgemacht.ai/api/mcp ABC123
```

`havi-setup` exchanges the short-lived setup code for a bearer token and writes
the hosted `/api/mcp` server into your Claude Code MCP config — no local server,
no binary to install. Restart Claude Code after setup completes.

The setup code expires quickly. Generate a fresh one on the `/try` connect page
each time you run `havi-setup`. Never paste a raw bearer token into the command;
always use a setup code from the connect page.
