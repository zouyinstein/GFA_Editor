#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="${GFA_EDITOR_PYTHON:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON="${GFA_EDITOR_PYTHON:-$(command -v python3 || true)}"
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "Python environment not found. Run: scripts/setup_local_dev.sh --desktop" >&2
  exit 1
fi

"$PYTHON" - <<'PY' >/dev/null 2>&1 || {
import webview
PY
  echo "Desktop dependencies are missing. Run: scripts/setup_local_dev.sh --desktop" >&2
  exit 1
}

exec "$PYTHON" desktop_app.py
