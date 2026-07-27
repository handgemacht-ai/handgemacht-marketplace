#!/usr/bin/env bash
# Validates the public marketplace package: structure, manifest parity, and that
# no published file leaks a private-repo URL or a raw user token.
# Relocated from havi test/havi/marketplace_package_test.exs when the package
# stopped being vendored inside the havi repo.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_MP="$ROOT/.claude-plugin/marketplace.json"
CODEX_MP="$ROOT/.agents/plugins/marketplace.json"
HOMEPAGE="https://github.com/handgemacht-ai/handgemacht-marketplace"
fail=0
err() { echo "FAIL: $*" >&2; fail=1; }
jqr() { jq -r "$2" "$1" 2>/dev/null || true; }
jqn() { jq -r --arg n "$2" "$3" "$1" 2>/dev/null || true; }
eq() { [ "$1" = "$2" ] || err "$3 (got: '$1', want: '$2')"; }
present() { [ -n "$1" ] && [ "$1" != "null" ] || err "$2 (missing)"; }

for f in "$CLAUDE_MP" "$CODEX_MP"; do
  [ -f "$f" ] || { echo "FAIL: missing marketplace manifest ${f#"$ROOT"/}" >&2; exit 1; }
done

# 1. Marketplace roots carry the package identity both clients read.
eq "$(jqr "$CLAUDE_MP" '.name')" "handgemacht" "claude marketplace name"
eq "$(jqr "$CLAUDE_MP" '.owner.name')" "handgemacht-ai" "claude marketplace owner"
eq "$(jqr "$CODEX_MP" '.name')" "handgemacht" "codex marketplace name"
eq "$(jqr "$CODEX_MP" '.interface.displayName')" "HAVI" "codex displayName"

# 2. Every plugin directory is a complete, registered package. Plugins are looked
# up by name, never by array position, so a new plugin may be listed in any order.
# A plugin belongs in the Codex marketplace exactly when it ships a Codex manifest:
# hooks-only plugins are Claude Code only and must stay out of the Codex manifest.
for dir in "$ROOT"/plugins/*/; do
  name="$(basename "$dir")"
  claude_manifest="${dir}.claude-plugin/plugin.json"
  codex_manifest="${dir}.codex-plugin/plugin.json"

  if [ ! -f "$claude_manifest" ]; then
    err "plugins/$name has no .claude-plugin/plugin.json; an unfinished package must not be committed"
    continue
  fi

  eq "$(jqr "$claude_manifest" '.name')" "$name" "plugins/$name plugin.json name"
  present "$(jqr "$claude_manifest" '.version')" "plugins/$name plugin.json version"
  present "$(jqr "$claude_manifest" '.description')" "plugins/$name plugin.json description"

  eq "$(jqn "$CLAUDE_MP" "$name" '[.plugins[] | select(.name == $n)] | length')" "1" \
    "plugins/$name listed exactly once in the claude marketplace"
  eq "$(jqn "$CLAUDE_MP" "$name" '.plugins[] | select(.name == $n) | .source')" "./plugins/$name" \
    "claude marketplace source for $name"
  eq "$(jqn "$CLAUDE_MP" "$name" '.plugins[] | select(.name == $n) | .homepage')" "$HOMEPAGE" \
    "claude marketplace homepage for $name"

  codex_entries="$(jqn "$CODEX_MP" "$name" '[.plugins[] | select(.name == $n)] | length')"
  if [ -f "$codex_manifest" ]; then
    eq "$(jqr "$codex_manifest" '.name')" "$name" "plugins/$name codex plugin.json name"
    eq "$(jqr "$claude_manifest" '.version')" "$(jqr "$codex_manifest" '.version')" \
      "plugins/$name manifest version parity"
    eq "$codex_entries" "1" "plugins/$name ships a codex manifest and must be listed in the codex marketplace"
    eq "$(jqn "$CODEX_MP" "$name" '.plugins[] | select(.name == $n) | .source.source')" "local" \
      "codex source.source for $name"
    eq "$(jqn "$CODEX_MP" "$name" '.plugins[] | select(.name == $n) | .source.path')" "./plugins/$name" \
      "codex source.path for $name"
    eq "$(jqn "$CODEX_MP" "$name" '.plugins[] | select(.name == $n) | .policy.installation')" "AVAILABLE" \
      "codex policy.installation for $name"
    eq "$(jqn "$CODEX_MP" "$name" '.plugins[] | select(.name == $n) | .policy.authentication')" "ON_USE" \
      "codex policy.authentication for $name"
    present "$(jqn "$CODEX_MP" "$name" '.plugins[] | select(.name == $n) | .category')" \
      "codex category for $name"
  else
    eq "$codex_entries" "0" "plugins/$name ships no codex manifest and must stay out of the codex marketplace"
  fi

  if command -v claude >/dev/null 2>&1; then
    claude plugin validate "$dir" >/dev/null 2>&1 || err "claude plugin validate rejected plugins/$name"
  fi
done

# 3. Neither marketplace may advertise a plugin the package does not contain.
while IFS= read -r name; do
  [ -d "$ROOT/plugins/$name" ] || err "claude marketplace lists '$name' but plugins/$name does not exist"
done < <(jqr "$CLAUDE_MP" '.plugins[].name')
while IFS= read -r name; do
  [ -d "$ROOT/plugins/$name" ] || err "codex marketplace lists '$name' but plugins/$name does not exist"
done < <(jqr "$CODEX_MP" '.plugins[].name')

# 4. havi's own contract: Claude Code bundles the hosted MCP server so `/mcp` can
# log in via OAuth. Codex has no in-app OAuth and still connects through the
# havi-setup runner, so it must not declare a bundled server.
claude="$ROOT/plugins/havi/.claude-plugin/plugin.json"
codex="$ROOT/plugins/havi/.codex-plugin/plugin.json"
eq "$(jqr "$claude" '.mcpServers')" "./.mcp.json" "claude plugin.json must bundle ./.mcp.json"
eq "$(jqr "$codex" 'has("mcpServers")')" "false" "codex plugin.json must not declare mcpServers"
eq "$(jqr "$codex" '.skills')" "./skills/" "codex skills path"
mcp="$ROOT/plugins/havi/.mcp.json"
[ -f "$mcp" ] || err "plugins/havi/.mcp.json missing"
eq "$(jqr "$mcp" '.mcpServers.havi.type')" "http" "bundled mcp server must use http transport"
grep -q "/api/mcp" "$mcp" || err "bundled mcp server must point at the hosted /api/mcp endpoint"

# 5. Public package includes setup runner and public installer
inst="$ROOT/install.sh"
setup="$ROOT/plugins/havi/bin/havi-setup"
grep -q "handgemacht-ai/handgemacht-marketplace" "$inst" || err "installer must reference the public marketplace"
grep -q "releases/latest/download" "$inst" || err "installer must use public release downloads"
grep -q "/api/setup/link/exchange" "$setup" || err "setup runner must call the link exchange endpoint"
grep -q "claude mcp add" "$setup" || err "setup runner must register the MCP server"
grep -q "device_code" "$setup" || err "setup runner must use device_code login"
grep -q "x-havi-workspace-id" "$setup" || err "setup runner must send the workspace header"

# 6. Published files must not depend on the private repo or carry raw tokens.
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
