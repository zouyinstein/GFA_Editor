<p align="center">
  <img src="frontend/app-icon.png" alt="GFA Editor app icon" width="96">
</p>

# GFA Editor v1.3.3

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

## Command Line

GFA Editor also ships a CLI wrapper for the core viewer/editor operations:

```bash
scripts/gfa_editor_cli.py --help
```

Draw a graph image. The output extension can be `.png`, `.svg`, or `.pdf`.
For `.svg` and `.pdf` Bandage output, the CLI uses the same GUI exporter, including minimap2/BLAST alignment colouring and light hit backgrounds:

```bash
scripts/gfa_editor_cli.py image graph.gfa graph.pdf --colour blastsolid --query multi_fasta.fa --alignment-tool minimap2 --alignment-args "-x asm5 -c --secondary=yes"
```

If `blastn` or `minimap2` is on `PATH`, the CLI uses it for query alignment. If neither is available, it falls back to exact sequence matching. PNG output and `--alignment-tool exact` use the lightweight CLI renderer.

Automatically resolve eligible 2-in/2-out repeat nodes, then merge the resolved circular graph:

```bash
scripts/gfa_editor_cli.py auto-repeat graph.gfa graph.resolved.gfa --candidate 1
scripts/gfa_editor_cli.py merge graph.resolved.gfa graph.merged.gfa --all
```

Use `--candidate 0` to write every auto-repeat candidate. Output files are named from the requested path, for example `graph.resolved.auto_repeat_001.gfa`, `graph.resolved.auto_repeat_002.gfa`, and so on. Candidate numbers are assigned deterministically from the head-to-tail continuous sequence features after each candidate is merged, so rerunning the same input keeps the same candidate number for the same merged arrangement.

The same workflow can be run as one command:

```bash
scripts/gfa_editor_cli.py auto-merge graph.gfa graph.merged.gfa --resolved-output graph.resolved.gfa
```

For a second sample with multiple possible resolutions, choose the candidate whose merged sequence is most continuously similar to an existing reference merged graph:

```bash
scripts/gfa_editor_cli.py auto-merge graph2.gfa graph2.merged.gfa --reference-merged graph.merged.gfa --resolved-output graph2.resolved.gfa
```

The same reference-guided selection can use a FASTA sequence directly:

```bash
scripts/gfa_editor_cli.py auto-repeat graph2.gfa graph2.resolved.gfa --reference-fasta reference.fa
scripts/gfa_editor_cli.py auto-merge graph2.gfa graph2.merged.gfa --reference-fasta reference.fa --resolved-output graph2.resolved.gfa
```

The reference selector first merges each candidate, then scores exact circular sequence matches and long continuous collinear k-mer chains against the reference merged sequence or FASTA record. Multi-record FASTA files are supported; each candidate is scored against the best-matching record. A manually supplied `--candidate` overrides this automatic reference selection.

Other scripted operations mirror common toolbar actions:

```bash
scripts/gfa_editor_cli.py stats graph.gfa
scripts/gfa_editor_cli.py --version
scripts/gfa_editor_cli.py export graph.gfa graph.fa --format fasta
scripts/gfa_editor_cli.py duplicate graph.gfa duplicated.gfa utg12
scripts/gfa_editor_cli.py repeat duplicated.gfa resolved.gfa utg12 utg12_copy1 --strategy A
scripts/gfa_editor_cli.py update-node graph.gfa labeled.gfa utg12 --label repeat --color '#2f6faf'
```

The macOS standalone app can also be used directly as the same CLI when launched from a terminal with arguments:

```bash
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor auto-repeat graph.gfa graph.resolved.gfa --candidate 0
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor --version
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor auto-merge graph.gfa graph.merged.gfa --candidate 2 --resolved-output graph.resolved.gfa
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor auto-repeat graph.gfa graph.resolved.gfa --reference-fasta reference.fa
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor image graph.gfa graph.pdf --colour blastsolid --query multi_fasta.fa --alignment-tool minimap2 --alignment-args "-x asm5 -c --secondary=yes"
```

Double-clicking the app, or launching it without CLI arguments, still opens the desktop GUI.

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

Large GFA files are checked as soon as they are loaded. Files with more than 200 nodes are split automatically into connected subgraph views, so there is no required manual "max elements per view" setting. Single-edge and isolated leftover nodes are sorted by contig length and split into `remaining_part_1`, `remaining_part_2`, and later chunks instead of one oversized Remaining view. The default chunk size is 50 nodes and can be changed in the Import panel before loading a GFA.

When a graph is split, use the Subgraph selector in the top toolbar to switch between views. Each option stays in the compact format `subgraph_1, 81 nodes, 103 links`; leftover chunks are shown as `remaining_part_1, ... nodes, ... links`.

GFA links are normalized on import, render, edit, and export. Reciprocal endpoint records such as the paired hifiasm `+/+` and `-/-` links are shown as one logical link in Cose, Band, and Twin views, matching the single-link behavior expected for Flye-style files.

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
