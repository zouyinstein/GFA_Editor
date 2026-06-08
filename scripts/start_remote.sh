#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/start_remote.sh <data-dir>

Starts one remote GFA Editor service for one user or task.

Required:
  <data-dir>  A unique server-side folder for this service's files.

Optional environment variables:
  GFA_EDITOR_PUBLIC_HOST=192.168.220.49  Public server IP/host shown in the URL.
  GFA_EDITOR_PORT=8000                  Preferred starting port. Defaults to 8000.
  GFA_EDITOR_HOST=0.0.0.0               Bind host. Defaults to 0.0.0.0.
  GFA_EDITOR_LOG=/path/to/log           Log file. Defaults to .local/gfa-editor-<port>.log.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  echo "Error: please provide a unique data directory for this remote service." >&2
  usage >&2
  exit 2
fi

HOST="${GFA_EDITOR_HOST:-0.0.0.0}"
HEALTH_HOST="$HOST"
if [[ "$HOST" == "0.0.0.0" ]]; then
  HEALTH_HOST="127.0.0.1"
fi
PREFERRED_PORT="${GFA_EDITOR_PORT:-8000}"
RAW_DATA_DIR="$1"

if [[ "$RAW_DATA_DIR" == "~" ]]; then
  DATA_DIR="$HOME"
elif [[ "$RAW_DATA_DIR" == "~/"* ]]; then
  DATA_DIR="$HOME/${RAW_DATA_DIR#"~/"}"
elif [[ "$RAW_DATA_DIR" == /* ]]; then
  DATA_DIR="$RAW_DATA_DIR"
else
  DATA_DIR="$PWD/$RAW_DATA_DIR"
fi

if ! [[ "$PREFERRED_PORT" =~ ^[0-9]+$ ]] || (( PREFERRED_PORT < 1 || PREFERRED_PORT > 65535 )); then
  echo "Error: GFA_EDITOR_PORT must be a TCP port between 1 and 65535." >&2
  exit 2
fi

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

detect_public_host() {
  local host_candidates token
  if [[ -n "${GFA_EDITOR_PUBLIC_HOST:-}" ]]; then
    echo "$GFA_EDITOR_PUBLIC_HOST"
    return 0
  fi
  if command -v hostname >/dev/null 2>&1; then
    host_candidates="$(hostname -I 2>/dev/null || true)"
    for token in $host_candidates; do
      if [[ "$token" == *.* && "$token" != 127.* ]]; then
        echo "$token"
        return 0
      fi
    done
  fi
  if command -v ip >/dev/null 2>&1; then
    token="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}' || true)"
    if [[ -n "$token" ]]; then
      echo "$token"
      return 0
    fi
  fi
  if [[ "$HOST" == "0.0.0.0" ]]; then
    echo "127.0.0.1"
  else
    echo "$HOST"
  fi
}

list_listening_ports_by_pid() {
  local line pid name port state recvq sendq local_addr rest
  if command -v lsof >/dev/null 2>&1; then
    pid=""
    while IFS= read -r line; do
      case "$line" in
        p*) pid="${line#p}" ;;
        n*)
          name="${line#n}"
          port="${name##*:}"
          if [[ "$port" =~ ^[0-9]+$ && -n "$pid" ]]; then
            echo "$pid $port"
          fi
          ;;
      esac
    done < <(lsof -nP -iTCP -sTCP:LISTEN -F pn 2>/dev/null || true)
    return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    while read -r state recvq sendq local_addr rest; do
      port="${local_addr##*:}"
      if [[ "$port" =~ ^[0-9]+$ && "$rest" =~ pid=([0-9]+) ]]; then
        echo "${BASH_REMATCH[1]} $port"
      fi
    done < <(ss -ltnpH 2>/dev/null || true)
  fi
}

list_gfa_editor_ports() {
  local pid port command_line
  while read -r pid port; do
    if [[ -z "${pid:-}" || -z "${port:-}" ]]; then
      continue
    fi
    command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
    if [[ "$command_line" == *"uvicorn backend.main:app"* || "$command_line" == *"backend.main:app"* ]]; then
      echo "$port"
    fi
  done < <(list_listening_ports_by_pid)
}

list_registered_gfa_editor_ports() {
  local pid_file filename pid port
  shopt -s nullglob
  for pid_file in "$ROOT_DIR"/.local/gfa-editor-*.pid; do
    filename="${pid_file##*/}"
    port="${filename#gfa-editor-}"
    port="${port%.pid}"
    if ! [[ "$port" =~ ^[0-9]+$ ]]; then
      continue
    fi
    pid="$(cat "$pid_file" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "$port"
    fi
  done
  shopt -u nullglob
}

health_check_url() {
  "$PYTHON" - "$1" <<'PY' >/dev/null 2>&1
import sys
from urllib.request import urlopen
urlopen(sys.argv[1] + "/api/health", timeout=1).read()
PY
}

port_available() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
      return 1
    fi
    return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    if [[ -n "$(ss -ltnH "sport = :$port" 2>/dev/null || true)" ]]; then
      return 1
    fi
    return 0
  fi
  "$PYTHON" - "$HEALTH_HOST" "$port" <<'PY' >/dev/null 2>&1
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.25)
    if sock.connect_ex((host, port)) == 0:
        sys.exit(1)
PY
}

find_free_port() {
  local port="$1"
  while (( port <= 65535 )); do
    if port_available "$port"; then
      echo "$port"
      return 0
    fi
    port=$((port + 1))
  done
  return 1
}

start_server() {
  if command -v setsid >/dev/null 2>&1; then
    nohup setsid "$PYTHON" -m uvicorn backend.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
  else
    nohup "$PYTHON" -m uvicorn backend.main:app --host "$HOST" --port "$PORT" > "$LOG_FILE" 2>&1 &
  fi
}

if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON="${GFA_EDITOR_PYTHON:-$ROOT_DIR/.venv/bin/python}"
else
  PYTHON="${GFA_EDITOR_PYTHON:-$(command -v python3 || true)}"
fi

if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  echo "Python environment not found. Run: bash scripts/setup_local_dev.sh" >&2
  exit 1
fi

"$PYTHON" - <<'PY' >/dev/null 2>&1 || {
import fastapi, uvicorn
PY
  echo "Python dependencies are missing. Run: bash scripts/setup_local_dev.sh" >&2
  exit 1
}

mkdir -p "$ROOT_DIR/.local" "$DATA_DIR"

SERVICE_FILE="$DATA_DIR/.gfa-editor-service"
if [[ -f "$SERVICE_FILE" ]]; then
  existing_pid="$(awk -F= '$1 == "PID" {print $2}' "$SERVICE_FILE" 2>/dev/null || true)"
  existing_port="$(awk -F= '$1 == "PORT" {print $2}' "$SERVICE_FILE" 2>/dev/null || true)"
  existing_url="$(awk -F= '$1 == "URL" {print $2}' "$SERVICE_FILE" 2>/dev/null || true)"
  if [[ -n "$existing_pid" && -n "$existing_port" ]] && kill -0 "$existing_pid" >/dev/null 2>&1; then
    existing_health_url="$(awk -F= '$1 == "HEALTH_URL" {print $2}' "$SERVICE_FILE" 2>/dev/null || true)"
    if health_check_url "${existing_health_url:-http://${HEALTH_HOST}:${existing_port}}"; then
      echo "This data directory already has a running GFA Editor service."
      echo "Data directory: $DATA_DIR"
      echo "Open: ${existing_url:-http://$(detect_public_host):${existing_port}/}"
      echo "PID: $existing_pid"
      echo "Stop: GFA_EDITOR_PORT=$existing_port bash scripts/stop_local.sh"
      exit 0
    fi
  fi
  rm -f "$SERVICE_FILE"
fi

GFA_PORTS="$({ list_registered_gfa_editor_ports; list_gfa_editor_ports; } | sort -n | uniq | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
GFA_PORT_COUNT=0
for _port in $GFA_PORTS; do
  GFA_PORT_COUNT=$((GFA_PORT_COUNT + 1))
done

echo "GFA Editor occupied port count on this server: $GFA_PORT_COUNT"

PORT="$(find_free_port "$PREFERRED_PORT")" || {
  echo "Error: no free TCP port found from $PREFERRED_PORT to 65535." >&2
  exit 1
}

if [[ "$PORT" != "$PREFERRED_PORT" ]]; then
  echo "Preferred port $PREFERRED_PORT is unavailable; using recommended free port $PORT."
fi

PUBLIC_HOST="$(detect_public_host)"
URL="http://${PUBLIC_HOST}:${PORT}/"
HEALTH_URL="http://${HEALTH_HOST}:${PORT}"
PID_FILE="$ROOT_DIR/.local/gfa-editor-${PORT}.pid"
LOG_FILE="${GFA_EDITOR_LOG:-$ROOT_DIR/.local/gfa-editor-${PORT}.log}"

export GFA_EDITOR_DATA_DIR="$DATA_DIR"
export PATH="$ROOT_DIR/packaging/bin/$(platform_key):$PATH"

start_server
pid=$!
echo "$pid" > "$PID_FILE"

{
  echo "PID=$pid"
  echo "PORT=$PORT"
  echo "URL=$URL"
  echo "HEALTH_URL=$HEALTH_URL"
  echo "DATA_DIR=$DATA_DIR"
  echo "LOG=$LOG_FILE"
} > "$SERVICE_FILE"

for _ in $(seq 1 40); do
  if health_check_url "$HEALTH_URL"; then
    echo "GFA Editor remote service started."
    echo "Data directory: $DATA_DIR"
    echo "Open: $URL"
    echo "PID: $pid"
    echo "Log: $LOG_FILE"
    echo "Stop: GFA_EDITOR_PORT=$PORT bash scripts/stop_local.sh"
    exit 0
  fi
  sleep 0.25
done

if kill -0 "$pid" >/dev/null 2>&1; then
  kill "$pid" >/dev/null 2>&1 || true
fi
rm -f "$PID_FILE" "$SERVICE_FILE"
echo "The remote server did not become ready. Check the log: $LOG_FILE" >&2
exit 1
