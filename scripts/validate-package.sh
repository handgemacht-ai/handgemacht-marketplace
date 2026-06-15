#!/usr/bin/env bash
# Validates the public marketplace package: structure, manifest parity, and that
# no published file leaks a private-repo URL or a raw user token.
# Relocated from havi test/havi/marketplace_package_test.exs when the package
# stopped being vendored inside the havi repo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLUGIN_PATH="./plugins/havi"
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }
jqr() { jq -r "$2" "$1" 2>/dev/null || true; }
eq() { [ "$1" = "$2" ] || err "$3 (got: '$1', want: '$2')"; }

# 1. Claude Code marketplace points at the staged public plugin package
f="$ROOT/.claude-plugin/marketplace.json"
eq "$(jqr "$f" '.name')" "handgemacht" "claude marketplace name"
eq "$(jqr "$f" '.owner.name')" "handgemacht-ai" "claude marketplace owner"
eq "$(jqr "$f" '.plugins[0].name')" "havi" "claude plugin name"
eq "$(jqr "$f" '.plugins[0].source')" "$PLUGIN_PATH" "claude plugin source"
eq "$(jqr "$f" '.plugins[0].homepage')" "https://github.com/handgemacht-ai/handgemacht-marketplace" "claude plugin homepage"

# 2. Codex marketplace includes required policy and source metadata
f="$ROOT/.agents/plugins/marketplace.json"
eq "$(jqr "$f" '.name')" "handgemacht" "codex marketplace name"
eq "$(jqr "$f" '.interface.displayName')" "HAVI" "codex displayName"
eq "$(jqr "$f" '.plugins[0].name')" "havi" "codex plugin name"
eq "$(jqr "$f" '.plugins[0].source.source')" "local" "codex source.source"
eq "$(jqr "$f" '.plugins[0].source.path')" "$PLUGIN_PATH" "codex source.path"
eq "$(jqr "$f" '.plugins[0].policy.installation')" "AVAILABLE" "codex policy.installation"
eq "$(jqr "$f" '.plugins[0].policy.authentication')" "ON_USE" "codex policy.authentication"
eq "$(jqr "$f" '.plugins[0].category')" "Developer Tools" "codex category"

# 3. Staged plugin package has Claude Code and Codex manifests
claude="$ROOT/plugins/havi/.claude-plugin/plugin.json"
codex="$ROOT/plugins/havi/.codex-plugin/plugin.json"
eq "$(jqr "$claude" '.name')" "havi" "claude plugin.json name"
eq "$(jqr "$codex" '.name')" "havi" "codex plugin.json name"
eq "$(jqr "$claude" '.version')" "$(jqr "$codex" '.version')" "manifest version parity"
eq "$(jqr "$claude" 'has("mcpServers")')" "false" "claude plugin.json must not declare mcpServers"
eq "$(jqr "$codex" 'has("mcpServers")')" "false" "codex plugin.json must not declare mcpServers"
eq "$(jqr "$codex" '.skills')" "./skills/" "codex skills path"
[ ! -f "$ROOT/plugins/havi/.mcp.json" ] || err "plugins/havi/.mcp.json must not be published"
[ -f "$ROOT/plugins/havi/hooks/hooks.json" ] || err "plugins/havi/hooks/hooks.json missing"

# 4. Public package includes setup runner and public installer
inst="$ROOT/install.sh"
setup="$ROOT/plugins/havi/bin/havi-setup"
grep -q "handgemacht-ai/handgemacht-marketplace" "$inst" || err "installer must reference the public marketplace"
grep -q "releases/latest/download" "$inst" || err "installer must use public release downloads"
grep -q "/api/setup/link/exchange" "$setup" || err "setup runner must call the link exchange endpoint"
grep -q "claude mcp add" "$setup" || err "setup runner must register the MCP server"
grep -q "device_code" "$setup" || err "setup runner must use device_code login"
grep -q "x-havi-workspace-id" "$setup" || err "setup runner must send the workspace header"

# 5. Published files must not depend on the private repo or carry raw tokens.
# Patterns are assembled from parts so this validator never matches itself.
priv="handgemacht-ai/havi"
patterns=(
  "raw.githubusercontent.com/${priv}(/|\$)"
  "github.com/${priv}(/|\$)"
  "user_token"
  "bearer[[:space:]]+[[:alnum:]_.-]{20,}"
)
oldifs=$IFS
IFS='|'
joined="${patterns[*]}"
IFS=$oldifs
while IFS= read -r -d '' file; do
  if grep -nEi "$joined" "$file" >/dev/null 2>&1; then
    err "forbidden pattern in ${file#"$ROOT"/}"
  fi
done < <(find "$ROOT" -type f -not -path '*/.git/*' -not -path '*/scripts/*' -print0)

if [ "$fail" -ne 0 ]; then
  echo "Marketplace package validation FAILED." >&2
  exit 1
fi
echo "Marketplace package validation passed."
