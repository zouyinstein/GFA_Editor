<p align="center">
  <img src="frontend/app-icon.png" alt="GFA Editor app icon" width="96">
</p>

# GFA Editor v1.2.3

GFA Editor is a local Bandage-style viewer and editor for GFA assembly graphs. It provides Cose, Band, and Twin visualization modes, graph editing, alignment visualization, local/server file management, and GFA, FASTA, SVG, and PDF export.

Unless you explicitly configure a server data directory or use SFTP transfer, your data stays on the local machine.

## License

GFA Editor source code is licensed under the **GNU Affero General Public License v3.0 or later**. The SPDX identifier is `AGPL-3.0-or-later`. See [LICENSE](LICENSE) for the full license text and [NOTICE](NOTICE) for copyright, branding, and third-party dependency notes.

This means future forks, modified versions, or redistributions cannot remove the AGPL obligations that already apply to the original code. If someone distributes a modified version, or provides a modified version as a network service, they should provide the corresponding source code under the AGPL. Third-party vendor files retain their own licenses.

## Quick Start

```bash
cd "/path/to/GFA_Editor"
scripts/setup_local_dev.sh
scripts/start_local.sh
```

Open:

```text
http://127.0.0.1:8000
```

Stop the service:

```bash
scripts/stop_local.sh
```

## Linux Server Access

To run GFA Editor on a Linux server and open it from another computer on the same network:

1. Download or unzip `GFA_Editor-main` on the server, then enter the project directory:

```bash
cd /home/zouyi/GFA_Editor-main
```

Replace `/home/zouyi/GFA_Editor-main` with the actual server path if you installed it elsewhere.

2. Install the local Python environment and dependencies:

```bash
bash scripts/setup_local_dev.sh
```

3. Start one remote service. The script creates a new `gfa_editor_task_N` data directory under the current directory:

```bash
cd /home/zouyi
GFA_EDITOR_PUBLIC_HOST=192.168.220.49 bash /home/zouyi/GFA_Editor-main/scripts/start_remote.sh
```

This creates `/home/zouyi/gfa_editor_task_1` for the first task, then `/home/zouyi/gfa_editor_task_2`, `/home/zouyi/gfa_editor_task_3`, and so on for later tasks.

You can also choose a parent folder explicitly. Reusing the same parent folder is safe because the script always creates the next unused task subfolder:

```bash
GFA_EDITOR_PUBLIC_HOST=192.168.220.49 bash /home/zouyi/GFA_Editor-main/scripts/start_remote.sh /home/zouyi/gfa-editor-data
```

The script binds the service to `0.0.0.0`, starts from port `8000`, checks which GFA Editor ports are already occupied on the server, prints the occupied-port count, and automatically chooses the next free port if needed.

4. Open the address printed by the script from the client computer:

```text
http://192.168.220.49:8000/
```

The actual port may be `8000` or another automatically recommended free port, such as `8001`.

### Per-User Remote Services

Use one server process per user or task. Each service gets a different auto-created data directory so saved server files, edits, and operation history do not interfere with another user's work.

To start another independent service, run the same command again. If the same parent folder already contains `gfa_editor_task_1`, the script creates `gfa_editor_task_2`:

```bash
GFA_EDITOR_PUBLIC_HOST=192.168.220.49 bash /home/zouyi/GFA_Editor-main/scripts/start_remote.sh /home/zouyi/gfa-editor-data
```

If port `8000` is already unavailable, the script does not ask you to type another port. It reports how many GFA Editor ports are occupied, selects a free port, starts the service, and prints the new access URL.

If the page cannot be reached, allow the printed TCP port through the server firewall.

For the local `scripts/start_local.sh` helper only, you can still choose another port manually:

```bash
GFA_EDITOR_PORT=8010 scripts/start_local.sh
GFA_EDITOR_PORT=8010 scripts/stop_local.sh
```

If startup says the port is in use but `/api/health` does not respond, another local process may be using the port. Find and stop it:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <PID>
```

Replace `8000` with the actual port. If you do not want to stop that process, start GFA Editor on a free port instead.

## Basic Usage

1. In the left Import panel, choose a `.gfa` file and click Load. You can also load files from the server data directory through the Files button in the top toolbar.
2. Use the Cose, Band, and Twin buttons in the top toolbar to switch visualization modes.
3. Use Display, Filters, Drawing, Labels, and Files to adjust rendering, filtering, drawing scope, labels, and file sources.
4. Select a contig or link in the graph, then inspect and edit it in the right Inspector panel.
5. Hold Shift and drag on empty graph space to marquee-select multiple graph items. Band and Twin Band view select both contigs and links inside the selection box.
6. Top toolbar actions include Undo, Redo, Delete, Delete All Selected, Duplicate, Merge, Rotate, and Repeat resolution.
7. The left Alignments panel can run or import alignment results. Use `f`, `b`, and the color picker to control each query.
8. The export controls on the top right support GFA, FASTA, current-view SVG/PDF, selected subgraph export, and edit history JSON.

For detailed usage, see [docs/user_manual.md](docs/user_manual.md).

## Desktop App

Install desktop dependencies:

```bash
scripts/setup_local_dev.sh --desktop
```

Run the desktop wrapper:

```bash
scripts/run_desktop.sh
```

Build for the current platform:

```bash
scripts/build_desktop_app.sh
```

macOS output:

```text
dist/GFA_Editor.app
```

Build the Windows 11 x86_64 executable:

```powershell
scripts\build_windows_exe.ps1
```

Windows output:

```text
dist\GFA_Editor\GFA_Editor.exe
```

When distributing the Windows build, share the whole `dist\GFA_Editor` folder. Do not copy only the `.exe`.

## Conda

```bash
conda env create -f environment.yml
conda activate gfa-editor
scripts/start_local.sh
```

The conda environment includes Python dependencies, `minimap2`, and BLAST.

## Docker

```bash
docker build -t gfa-editor .
docker run --rm -p 8000:8000 -v "$PWD/server_data:/data/gfa-editor" gfa-editor
```

Open:

```text
http://127.0.0.1:8000
```

## Alignment Tools

Running alignments requires `minimap2` or `blastn`. You can install them with conda:

```bash
conda install -c bioconda minimap2 blast
```

Collect alignment tools for the desktop or standalone package:

```bash
scripts/collect_alignment_tools.sh
```

## Example Data

```text
examples/mecat_mito_500K_before_rr.gfa
examples/simulated_reads/
```

## Data Directory

Default local data directory:

```text
server_data/
```

Use a custom local data directory:

```bash
GFA_EDITOR_DATA_DIR=/path/to/data scripts/start_local.sh
```
