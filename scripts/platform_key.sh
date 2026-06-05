#!/usr/bin/env bash
set -euo pipefail

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
