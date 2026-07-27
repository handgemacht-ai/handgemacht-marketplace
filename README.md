# HAVI Marketplace Staging Root

This directory is the source for a public `handgemacht-ai/handgemacht-marketplace`
repository. It keeps outside-user marketplace metadata separate from the private
HAVI application repository.

## User Install Commands

Claude Code:

```bash
claude plugin marketplace add handgemacht-ai/handgemacht-marketplace
claude plugin install havi@handgemacht
claude plugin install havi-plan@handgemacht
```

Inside Claude Code, the same flow is:

```text
/plugin marketplace add handgemacht-ai/handgemacht-marketplace
/plugin install havi@handgemacht
/plugin install havi-plan@handgemacht
```

Codex:

```bash
codex plugin marketplace add handgemacht-ai/handgemacht-marketplace
codex plugin add havi@handgemacht
```

`havi-plan` is Claude Code only. It ships a hook rather than an MCP server or a
skill, so it carries no Codex manifest and is absent from the Codex marketplace
file. A plugin appears in `.agents/plugins/marketplace.json` exactly when it
ships `.codex-plugin/plugin.json`, and `scripts/validate-package.sh` enforces
that in both directions.

## Public Repository Layout

```text
.
|-- .agents/plugins/marketplace.json
|-- .claude-plugin/marketplace.json
|-- install.sh
|-- scripts/
|   |-- run-plugin-tests.sh
|   `-- validate-package.sh
|-- plugins/havi/
|   |-- bin/havi-setup
|   |-- .claude-plugin/plugin.json
|   |-- .codex-plugin/plugin.json
|   |-- .mcp.json
|   |-- README.md
|   `-- skills/havi-setup/SKILL.md
`-- plugins/havi-plan/
    |-- .claude-plugin/plugin.json
    |-- hooks/hooks.json
    |-- hooks/plan-review.py
    |-- README.md
    `-- tests/test_plan_review.py
```

Every directory under `plugins/` must be a complete package: a
`.claude-plugin/plugin.json` whose name matches the directory, and an entry in
`.claude-plugin/marketplace.json`. Work in progress does not belong in the
published tree.

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
