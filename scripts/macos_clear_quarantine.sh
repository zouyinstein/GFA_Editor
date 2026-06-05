#!/usr/bin/env bash
set -euo pipefail

APP_PATH="${1:-dist/GFA_Editor.app}"

if [[ ! -d "$APP_PATH" ]]; then
  echo "App not found: $APP_PATH" >&2
  echo "Usage: scripts/macos_clear_quarantine.sh [path/to/GFA_Editor.app]" >&2
  exit 1
fi

xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
echo "Cleared macOS quarantine flag: $APP_PATH"
