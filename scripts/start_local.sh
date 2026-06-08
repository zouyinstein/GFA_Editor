#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

HOST="${GFA_EDITOR_HOST:-127.0.0.1}"
PORT="${GFA_EDITOR_PORT:-8000}"
HEALTH_HOST="$HOST"
DISPLAY_HOST="${GFA_EDITOR_PUBLIC_HOST:-$HOST}"
if [[ "$HOST" == "0.0.0.0" ]]; then
  HEALTH_HOST="127.0.0.1"
fi
URL="http://${DISPLAY_HOST}:${PORT}"
HEALTH_URL="http://${HEALTH_HOST}:${PORT}"
PID_DIR="$ROOT_DIR/.local"
PID_FILE="$PID_DIR/gfa-editor.pid"
LOG_FILE="${GFA_EDITOR_LOG:-$ROOT_DIR/uvicorn.log}"
DATA_DIR="${GFA_EDITOR_DATA_DIR:-$ROOT_DIR/server_data}"

platform_key() {
  local os_name arch_name
  os_name="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch_name="$(uname -m)"
  case "$os_name:$arch_name" in
    darwin:arm64) echo "macos-arm64" ;;
    darwin:x86_64) echo "macos-x86_64" ;;
    linux:aarch64|linux:arm64) echo "linux-arm64" ;;
    linux:x86_64) echo "linux-x86_64" ;;
    mingw*:*) echo "windows-x86_64" ;;
    msys*:*) echo "windows-x86_64" ;;
    cygwin*:*) echo "windows-x86_64" ;;
    *) echo "${os_name}-${arch_name}" ;;
  esac
}

open_url() {
  if [[ "${GFA_EDITOR_NO_OPEN:-0}" == "1" ]]; then
    return 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "$URL" >/dev/null 2>&1 || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "$URL" >/dev/null 2>&1 || true
  fi
}

health_check() {
  "$PYTHON" - "$HEALTH_URL" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen
urlopen(sys.argv[1] + "/api/health", timeout=1).read()
PY
}

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="${GFA_EDITOR_PYTHON:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON="${GFA_EDITOR_PYTHON:-$(command -v python3 || true)}"
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "Python environment not found. Run: scripts/setup_local_dev.sh" >&2
  exit 1
fi

"$PYTHON" - <<'PY' >/dev/null 2>&1 || {
import fastapi, uvicorn
PY
  echo "Python dependencies are missing. Run: scripts/setup_local_dev.sh" >&2
  exit 1
}

export GFA_EDITOR_DATA_DIR="$DATA_DIR"
export PATH="$ROOT_DIR/packaging/bin/$(platform_key):$PATH"
mkdir -p "$PID_DIR" "$DATA_DIR"

if health_check; then
  echo "GFA Editor is already running at $URL"
  open_url
  exit 0
fi

if command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port $PORT is already in use, but $URL did not answer /api/health." >&2
  echo "Stop the other process or set GFA_EDITOR_PORT to another port." >&2
  exit 1
fi

nohup "$PYTHON" -m uvicorn backend.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"

for _ in $(seq 1 40); do
  if health_check; then
    echo "GFA Editor started at $URL"
    echo "PID: $pid"
    echo "Log: $LOG_FILE"
    open_url
    exit 0
  fi
  sleep 0.25
done

if kill -0 "$pid" >/dev/null 2>&1; then
  kill "$pid" >/dev/null 2>&1 || true
fi
rm -f "$PID_FILE"
echo "The server did not become ready. Check the log: $LOG_FILE" >&2
exit 1
