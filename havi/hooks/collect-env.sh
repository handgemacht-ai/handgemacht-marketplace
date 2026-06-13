#!/usr/bin/env bash
# SessionStart hook: collect git context and inject annotation environment
# variables into the Claude env file. These are used by MCP URL interpolation
# and by skills for filtering annotations to the current branch/worktree.
set -euo pipefail

INPUT=$(cat)

MANAGED_BLOCK_START="# >>> annotation.collect_env >>>"
MANAGED_BLOCK_END="# <<< annotation.collect_env <<<"

# Extract cwd from SessionStart JSON input
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || true)
[ -z "$CWD" ] && CWD="$(pwd)"

# Collect git context (all commands fail gracefully)
BRANCH=$(git -C "$CWD" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
COMMIT=$(git -C "$CWD" rev-parse --short HEAD 2>/dev/null || true)
REPO=$(git -C "$CWD" remote get-url origin 2>/dev/null | sed 's|.*/||;s|\.git$||' || true)

# Detect worktree: if .git is a file (not directory), we're in a linked worktree
WORKTREE=""
if [ -f "$CWD/.git" ] 2>/dev/null; then
  WORKTREE=$(basename "$CWD")
elif git -C "$CWD" rev-parse --git-common-dir >/dev/null 2>&1; then
  GIT_COMMON=$(git -C "$CWD" rev-parse --git-common-dir 2>/dev/null || true)
  GIT_DIR=$(git -C "$CWD" rev-parse --git-dir 2>/dev/null || true)
  if [ -n "$GIT_COMMON" ] && [ -n "$GIT_DIR" ] && [ "$GIT_COMMON" != "$GIT_DIR" ]; then
    WORKTREE=$(basename "$CWD")
  fi
fi

# Write to CLAUDE_ENV_FILE using managed block pattern
[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0

mkdir -p "$(dirname "$CLAUDE_ENV_FILE")"

TMP_FILE=$(mktemp "${CLAUDE_ENV_FILE}.XXXXXX")
PRESERVED_FILE=$(mktemp "${CLAUDE_ENV_FILE}.preserved.XXXXXX")
trap 'rm -f "$TMP_FILE" "$PRESERVED_FILE"' EXIT

# Preserve lines from other plugins (outside our managed block)
if [ -f "$CLAUDE_ENV_FILE" ]; then
  awk -v start="$MANAGED_BLOCK_START" -v end="$MANAGED_BLOCK_END" '
    $0 == start { skip = 1; next }
    $0 == end { skip = 0; next }
    skip != 1 { print }
  ' "$CLAUDE_ENV_FILE" > "$PRESERVED_FILE"
else
  : > "$PRESERVED_FILE"
fi

{
  if [ -s "$PRESERVED_FILE" ]; then
    cat "$PRESERVED_FILE"
    printf '\n'
  fi

  printf '%s\n' "$MANAGED_BLOCK_START"
  [ -n "$BRANCH" ]   && printf 'export ANNOTATION_BRANCH=%q\n' "$BRANCH"
  [ -n "$COMMIT" ]    && printf 'export ANNOTATION_COMMIT=%q\n' "$COMMIT"
  [ -n "$REPO" ]      && printf 'export ANNOTATION_REPO=%q\n' "$REPO"
  [ -n "$WORKTREE" ]  && printf 'export ANNOTATION_WORKTREE=%q\n' "$WORKTREE"
  [ -n "$CWD" ]       && printf 'export ANNOTATION_CWD=%q\n' "$CWD"
  printf '%s\n' "$MANAGED_BLOCK_END"
} > "$TMP_FILE"

chmod 600 "$TMP_FILE"
mv "$TMP_FILE" "$CLAUDE_ENV_FILE"
rm -f "$PRESERVED_FILE"
