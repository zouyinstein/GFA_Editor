#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python3}"
INSTALL_DESKTOP="${INSTALL_DESKTOP:-0}"
if [[ "${1:-}" == "--desktop" ]]; then
  INSTALL_DESKTOP=1
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  echo "Install Python 3.10+ or set PYTHON_BIN=/path/to/python3." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt

if [[ "$INSTALL_DESKTOP" == "1" ]]; then
  .venv/bin/python -m pip install -r packaging/requirements-desktop.txt
fi

missing_tools=()
for tool in minimap2 blastn; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing_tools+=("$tool")
  fi
done

if [[ ${#missing_tools[@]} -gt 0 ]]; then
  echo
  echo "Python dependencies are ready, but these alignment tools were not found on PATH:"
  printf '  - %s\n' "${missing_tools[@]}"
  echo
  echo "Install them with one of these options:"
  echo "  conda install -c bioconda minimap2 blast"
  echo "  brew install minimap2 blast"
  echo
  echo "The app can still run, but Run alignment will need those tools."
fi

echo
echo "Setup complete."
echo "Start the app with: scripts/start_local.sh"
