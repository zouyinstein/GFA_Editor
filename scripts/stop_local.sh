#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${GFA_EDITOR_PORT:-8000}"
PID_FILES=("$ROOT_DIR/.local/gfa-editor-${PORT}.pid")
if [[ "$PORT" == "8000" ]]; then
  PID_FILES+=("$ROOT_DIR/.local/gfa-editor.pid")
fi

stop_pid() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  if ! kill -0 "$pid" >/dev/null 2>&1; then
    return 1
  fi
  kill "$pid" >/dev/null 2>&1 || return 1
  for _ in $(seq 1 20); do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.2
  done
  kill -TERM "$pid" >/dev/null 2>&1 || true
}

for PID_FILE in "${PID_FILES[@]}"; do
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE")"
    if stop_pid "$pid"; then
      rm -f "$PID_FILE"
      echo "Stopped GFA Editor PID $pid."
      exit 0
    fi
    rm -f "$PID_FILE"
  fi
done

if command -v lsof >/dev/null 2>&1; then
  pids="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
  for pid in $pids; do
    command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$command_line" == *"uvicorn backend.main:app"* || "$command_line" == *"backend.main:app"* ]]; then
      if stop_pid "$pid"; then
        echo "Stopped GFA Editor PID $pid."
        exit 0
      fi
    fi
  done
fi

echo "No running GFA Editor server found for port $PORT."
