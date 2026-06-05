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

"$PYTHON" - <<'PY' >/dev/null 2>&1 || "$PYTHON" -m pip install -r packaging/requirements-desktop.txt
import PyInstaller
import webview
PY

scripts/collect_alignment_tools.sh
"$PYTHON" scripts/generate_app_icons.py
export PYINSTALLER_CONFIG_DIR="$ROOT_DIR/.pyinstaller"
mkdir -p "$PYINSTALLER_CONFIG_DIR"
"$PYTHON" -m PyInstaller --noconfirm packaging/pyinstaller/gfa_editor_desktop.spec

echo
echo "Desktop build complete."
if [[ "$(uname -s)" == "Darwin" ]]; then
  echo "macOS app: dist/GFA_Editor.app"
else
  echo "Executable: dist/GFAEditor"
fi
