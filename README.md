# GFA Editor v1.0

Bandage-style GFA graph viewer and editor for local use. It supports graph drawing, basic GFA editing, GFA/FASTA export, read/alignment visualization, and local file management.

Data stays on the local machine unless a custom server directory or SFTP transfer is configured.

## Quick Start

Install the local environment:

```bash
cd "/path/to/bandage重构"
scripts/setup_local_dev.sh
```

Start the app:

```bash
scripts/start_local.sh
```

Open:

```text
http://127.0.0.1:8000
```

Stop the background service:

```bash
scripts/stop_local.sh
```

Use another port when `8000` is busy:

```bash
GFA_EDITOR_PORT=8010 scripts/start_local.sh
```

## Conda

```bash
conda env create -f environment.yml
conda activate gfa-editor
scripts/start_local.sh
```

The conda environment includes Python dependencies, `minimap2`, and BLAST.

## Docker

On macOS, Docker requires Docker Desktop or Colima in addition to the Docker CLI.

Colima setup:

```bash
brew install colima
colima start --arch aarch64 --cpu 2 --memory 4 --disk 20
docker context use colima
```

Build:

```bash
docker build -t gfa-editor .
```

Run:

```bash
docker run --rm \
  -p 8000:8000 \
  -v "$PWD/server_data:/data/gfa-editor" \
  gfa-editor
```

Open:

```text
http://127.0.0.1:8000
```

Alternative host port:

```bash
docker run --rm \
  -p 8015:8000 \
  -v "$PWD/server_data:/data/gfa-editor" \
  gfa-editor
```

Open:

```text
http://127.0.0.1:8015
```

## Desktop App

Install desktop dependencies:

```bash
scripts/setup_local_dev.sh --desktop
```

Run the desktop wrapper:

```bash
scripts/run_desktop.sh
```

Build the desktop app for the current platform:

```bash
scripts/build_desktop_app.sh
```

macOS output:

```text
dist/GFA_Editor.app
```

Windows 11 x86_64 build:

```powershell
scripts\build_windows_exe.ps1
```

Windows output:

```text
dist\GFA_Editor\GFA_Editor.exe
```

Share the whole `dist\GFA_Editor` folder on Windows. The folder contains the executable, Python runtime, frontend files, and bundled alignment tools.

The desktop wrapper opens an embedded WebView by default. If WebView fails on the current macOS environment, it opens the same local app in the system browser. Logs are written to:

```text
~/GFAEditorData/desktop.log
```

Force browser mode:

```bash
GFA_EDITOR_DESKTOP_MODE=browser scripts/run_desktop.sh
```

## macOS Gatekeeper

Unsigned local builds may show:

```text
Apple could not verify "GFA_Editor" is free of malware
```

Open a trusted local build with:

```text
Right click GFA_Editor.app -> Open -> Open
```

Or clear the quarantine flag:

```bash
scripts/macos_clear_quarantine.sh dist/GFA_Editor.app
```

Public macOS releases should be signed with Apple Developer ID and notarized.

## Quasi-Standalone Package

Build:

```bash
scripts/build_quasi_standalone.sh
```

Example output:

```text
dist/gfa-editor-local-macos-arm64/
```

Run inside the package:

```bash
./start.sh
```

macOS can also open:

```text
start.command
```

The package includes the project files, a local Python environment, start/stop scripts, and collected `minimap2` / `blastn` executables for the current platform.

## Alignment Tools

Run alignment requires:

```text
minimap2
blastn
```

Install with conda:

```bash
conda install -c bioconda minimap2 blast
```

Collect tools for desktop or standalone packaging:

```bash
scripts/collect_alignment_tools.sh
```

Collected tools are stored under:

```text
packaging/bin/<platform>/
```

## Example Data

Example GFA:

```text
examples/mecat_mito_500K_before_rr.gfa
```

Simulated reads and PAF files:

```text
examples/simulated_reads/
```

`edge8_repeat_long_reads.*` covers repeat-path visualization around `edge_8`.

`edge33_path_long_reads.*` covers partial edge hits and long reads crossing links.

## Data Directory

Default local data directory:

```text
server_data/
```

Custom local data directory:

```bash
GFA_EDITOR_DATA_DIR=/path/to/data scripts/start_local.sh
```

Docker data directory:

```text
/data/gfa-editor
```
