#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PLATFORM_KEY="$("$ROOT_DIR/scripts/platform_key.sh")"
DIST_DIR="${1:-$ROOT_DIR/dist/gfa-editor-local-$PLATFORM_KEY}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

copy_path() {
  local source="$1"
  if [[ -e "$source" ]]; then
    cp -R "$source" "$DIST_DIR/"
  fi
}

copy_path backend
copy_path frontend
copy_path examples
copy_path scripts
copy_path packaging
copy_path README.md
copy_path environment.yml
copy_path Dockerfile

mkdir -p "$DIST_DIR/server_data"

if [[ -d "$ROOT_DIR/.venv" && "${GFA_EDITOR_REBUILD_STANDALONE_VENV:-0}" != "1" ]]; then
  cp -R "$ROOT_DIR/.venv" "$DIST_DIR/.venv"
else
  "$PYTHON_BIN" -m venv "$DIST_DIR/.venv"
  "$DIST_DIR/.venv/bin/python" -m pip install --upgrade pip
  "$DIST_DIR/.venv/bin/python" -m pip install -r "$DIST_DIR/backend/requirements.txt"
fi

"$ROOT_DIR/scripts/collect_alignment_tools.sh" "$DIST_DIR/packaging/bin"

cat > "$DIST_DIR/start.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GFA_EDITOR_PYTHON="$ROOT_DIR/.venv/bin/python"
exec "$ROOT_DIR/scripts/start_local.sh"
SH

cat > "$DIST_DIR/stop.sh" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GFA_EDITOR_PYTHON="$ROOT_DIR/.venv/bin/python"
exec "$ROOT_DIR/scripts/stop_local.sh"
SH

cat > "$DIST_DIR/start.command" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export GFA_EDITOR_PYTHON="$ROOT_DIR/.venv/bin/python"
exec "$ROOT_DIR/scripts/start_local.sh"
SH

chmod +x "$DIST_DIR/start.sh" "$DIST_DIR/stop.sh" "$DIST_DIR/start.command"

echo
echo "Quasi-standalone package created:"
echo "  $DIST_DIR"
echo
echo "Run it with:"
echo "  $DIST_DIR/start.sh"
echo
echo "On macOS, users can also double-click:"
echo "  $DIST_DIR/start.command"
