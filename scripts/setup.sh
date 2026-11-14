#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
supported() {
  "$1" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)' >/dev/null 2>&1
}
chosen=""
if [[ -n "${QUICK_QUERY_PYTHON:-}" ]]; then
  if ! supported "$QUICK_QUERY_PYTHON"; then
    echo 'QUICK_QUERY_PYTHON must point to Python 3.11, 3.12, or 3.13.' >&2; exit 1
  fi
  chosen="$QUICK_QUERY_PYTHON"
elif [[ -x .venv/bin/python ]] && supported .venv/bin/python; then
  chosen="$(pwd)/.venv/bin/python"
else
  for candidate in python3.12 python3.13 python3.11 python3 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12; do
    if command -v "$candidate" >/dev/null 2>&1 && supported "$candidate"; then chosen="$(command -v "$candidate")"; break; fi
  done
fi
if [[ -z "$chosen" ]]; then
  echo 'Python 3.15 is not supported by these dependencies. Install Python 3.12: brew install python@3.12' >&2
  echo 'Then rerun: bash scripts/setup.sh (your default python3 is left unchanged).' >&2
  exit 1
fi
if [[ -d .venv ]] && ! supported .venv/bin/python; then
  backup=".venv-backup-$(date +%Y%m%d-%H%M%S)-$$"
  mv .venv "$backup"
  echo "Preserved incompatible environment as $backup"
fi
if [[ ! -x .venv/bin/python ]]; then "$chosen" -m venv .venv; fi
.venv/bin/python -m pip install --only-binary=:all: -c requirements-tested.txt '.[test]'
.venv/bin/quick-query quick-config --output quick-mcp.json
echo 'Ready. Start small: .venv/bin/quick-query demo-small'
echo 'Full public-data benchmark: .venv/bin/quick-query demo'
