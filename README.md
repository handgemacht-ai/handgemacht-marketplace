# HAVI Marketplace Staging Root

This directory is the source for a public `handgemacht-ai/handgemacht-marketplace`
repository. It keeps outside-user marketplace metadata separate from the private
HAVI application repository.

## User Install Commands

Claude Code:

```bash
claude plugin marketplace add handgemacht-ai/handgemacht-marketplace
claude plugin install havi@handgemacht
```

Inside Claude Code, the same flow is:

```text
/plugin marketplace add handgemacht-ai/handgemacht-marketplace
/plugin install havi@handgemacht
```

Codex:

```bash
codex plugin marketplace add handgemacht-ai/handgemacht-marketplace
codex plugin add havi@handgemacht
```

## Public Repository Layout

```text
.
|-- .agents/plugins/marketplace.json
|-- .claude-plugin/marketplace.json
|-- install.sh
`-- plugins/havi/
    |-- bin/havi-setup
    |-- .claude-plugin/plugin.json
    |-- .codex-plugin/plugin.json
    |-- .mcp.json
    |-- hooks/hooks.json
    |-- hooks/collect-env.sh
    |-- hooks/ensure-server.sh
    |-- README.md
    `-- skills/havi-setup/SKILL.md
```

The public repository must contain only marketplace metadata, public plugin
package files, and public setup docs. Do not publish private source code,
internal credentials, raw user tokens, or install URLs that depend on the
private `handgemacht-ai/havi` repository.

## Release Notes

- The staged package uses `./plugins/havi` as the plugin source for both Claude
  Code and Codex.
- Public binary downloads use releases from this public marketplace repository.
- Account linking should happen through HAVI login and workspace confirmation,
  not through dashboard copy that shows a long-lived token.
