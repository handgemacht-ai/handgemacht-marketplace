#!/usr/bin/env bash
# Runs the test suite of every plugin in the package. A plugin's suite lives in
# plugins/<name>/tests, so a newly added plugin is picked up without touching CI.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
found=0

for dir in "$ROOT"/plugins/*/; do
  name="$(basename "$dir")"
  tests="${dir}tests"
  [ -d "$tests" ] || continue
  found=1
  echo "== $name"
  python3 -m unittest discover -s "$tests" -p 'test_*.py'
done

if [ "$found" -ne 1 ]; then
  echo "No plugin test suite found under plugins/*/tests." >&2
  exit 1
fi
