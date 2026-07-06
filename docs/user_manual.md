# GFA Editor v1.3.3 User Manual

This manual describes the main tools and workflows in GFA Editor v1.3.3. GFA Editor is designed for local viewing, editing, alignment visualization, and export of GFA assembly graphs.

## 1. Start, Stop, and Data Safety

Start the local browser version:

```bash
scripts/start_local.sh
```

Open:

```text
http://127.0.0.1:8000
```

Stop:

```bash
scripts/stop_local.sh
```

If port `8000` is already in use:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <PID>
```

You can also keep the existing process running and use another port:

```bash
GFA_EDITOR_PORT=8010 scripts/start_local.sh
```

### Linux Server Access

To run GFA Editor on a Linux server and access it from another computer on the same network:

1. Download or unzip `GFA_Editor-main` on the server, then enter the project directory:

```bash
cd /home/zouyi/GFA_Editor-main
```

Replace `/home/zouyi/GFA_Editor-main` with the actual server path if needed.

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

If the browser cannot connect, allow the printed TCP port through the server firewall.

By default, GFA Editor only reads and writes data on your local machine. It interacts with external paths or remote servers only when you explicitly use the Files server data directory or SFTP features.

## 2. Interface Layout

The top bar shows the app icon, `GFA Editor v1.3.3`, and the current file name on the left. Visualization modes and tool buttons are in the middle. Editing and export buttons are on the right.

The left panel contains Stats, Import, Labels, and Alignments.

The center area is the graph workspace. The right side contains Inspector, Operation Log, and Edit History.

## 3. Import

Choose a `.gfa` file in the Import panel, then click Load.

`Keep sequences for GFA/FASTA export` preserves segment sequences. Keep it enabled if you need FASTA export or GFA export with sequences. Disable it only for very large graphs when sequence export is not needed.

You can also load graph files from the local server data directory or an SFTP path through the Files button in the top toolbar.

## 4. Visualization Modes

Cose is a force-directed layout for quickly inspecting graph connectivity.

Band is a Bandage-style layout. Contigs are rendered as thick paths and links are rendered as directional arrows.

Twin shows Cose and Band side by side, which is useful for comparing topology and path shape.

The Fit button centers the current visible graph and fits it to the viewport.

The Draw button redraws the graph. Drawing settings can choose the redraw scope:

- Entire graph: redraw the whole graph.
- Visible/filter result: redraw only the currently visible or filtered graph.
- Selected neighborhood: redraw the neighborhood of the selected contig.

`Redraw after edits` automatically redraws the graph after edits.

## 5. Display, Filters, Labels, and Files

Display adjusts zoom, circle size, contig width, and link width.

Filters searches contigs, switches between partial and exact matching, sets minimum depth, and selects the color mode. Color modes include depth, alignment identity, long-read paths, degree, and random.

Labels controls which text is shown:

- Name
- Length
- Depth
- Alignments
- Link label
- Text outline

Files contains local server data and SFTP actions. You can refresh the file list, load a server GFA file, save the current graph to the server data directory, download from SFTP, and upload to SFTP.

## 6. Selection and Inspector

Click a contig or link to select it. Multi-selection support and available actions depend on the current view and selection.

In Cose, Band, and the Band side of Twin view, hold Shift and drag on empty graph space to marquee-select multiple graph items. Band and Twin Band view select both contigs and links inside the selection box.

Inspector shows ID, label, length, depth, degree, support, CIGAR, tags, and available best alignment or path information.

Edit contig can modify:

- Name
- Label
- Colour
- Depth

Changing Name rewrites the GFA `S` record and updates related `L` records.

Edit link can modify:

- Label
- Colour
- Support RC
- CIGAR

Link label and colour are saved as `LB:Z` and `CL:Z` tags.

## 7. Editing Tools

Undo and Redo undo or redo graph edits.

Delete removes the current selection.

Delete All Selected removes all selected contigs and links.

Duplicate copies the selected contig and related links.

Merge merges the selected link, or merges a selected connected path. In Cose and Band views, merge adjusts only the merged contig and related links where possible. Unmerged contigs and links keep their previous positions as much as possible to reduce layout jumps.

Rotate changes the start position of a circular contig. It is enabled only when the selected contig has exactly one link and that link is a self-loop.

Repeat A and Repeat B are repeat-resolution tools. A typical workflow is to duplicate the repeat contig first, then apply Repeat A or Repeat B depending on the desired strategy.

Operation Log records recent operations. Its before and after buttons restore operation-level graph states, including upload, alignment, and delete-selection states.

Edit History can export, import, infer, render, and replay edit history.

## 8. Alignments

Alignments supports `minimap2` and `blastn`.

Run an alignment:

1. Load a GFA file.
2. Choose Tool.
3. Choose Preset.
4. Choose query FASTA/FASTQ.
5. Click Run.

Advanced contains extra args, imported result format, result target role, generated command preview, and import of existing PAF or BLAST outfmt 6 files.

The Read selector can show All reads or a single query/read.

Alignment color controls:

- `Light hit background` controls whether hit contigs may show a light background in alignment/read-path color modes.
- Query colours gives each query an `f` checkbox, a `b` checkbox, and a color picker.
- `f` means foreground. It controls whether the dark aligned segments for that query are shown.
- `b` means background. It controls whether that query contributes to the light hit background.
- For a single query, you can show a light hit-contig background while keeping the dark aligned segment visible.
- When `b` is disabled for a single query, the light background is hidden and only the dark aligned segment remains.
- For multiple queries, per-query light backgrounds are disabled by default. Dark aligned segments use different query colors.
- All hit contigs use one shared light background color, so the background is distinguishable from the unhit light gray graph background and remains readable when several queries overlap.

For example, three queries can show red, blue, and green dark aligned segments. If background is enabled, a shared light color marks contigs that were hit.

## 9. Export

The quick export button on the top right saves the current graph with a default file name.

Export options include:

- GFA: save the current graph as GFA
- FASTA: save the current graph as FASTA
- SVG: save the current view as SVG
- PDF: save the current view as a vector PDF
- Selected: export selected links as GFA
- History: export edit history JSON

In browser mode, export opens a save-file dialog so you can choose a path and rename the file instead of immediately downloading.

In the macOS standalone app, export uses the system file picker so you can choose the save location and file name.

SVG and PDF export preserve visible labels, colors, and alignment foreground hit segments from the current Cose, Band, or Twin view. Exported SVG paths include explicit no-fill and stroke attributes for better compatibility with vector editors such as Affinity Designer and system preview tools.

## 10. Command Line

The CLI exposes common GFA Editor operations for scripted runs:

```bash
scripts/gfa_editor_cli.py --help
```

Draw a graph image:

```bash
scripts/gfa_editor_cli.py image graph.gfa graph.pdf --colour blastsolid --query multi_fasta.fa --alignment-tool minimap2 --alignment-args "-x asm5 -c --secondary=yes"
```

Image output supports `.png`, `.svg`, and `.pdf`. For `.svg` and `.pdf` Bandage output, the CLI uses the same GUI exporter, including minimap2/BLAST alignment colouring and light hit backgrounds. Query colouring uses `blastn` or `minimap2` when available and falls back to exact sequence matching if neither tool is installed; PNG output and `--alignment-tool exact` use the lightweight CLI renderer.

Resolve eligible 2-in/2-out repeat nodes and merge the resolved circular graph:

```bash
scripts/gfa_editor_cli.py auto-repeat graph.gfa graph.resolved.gfa --candidate 1
scripts/gfa_editor_cli.py merge graph.resolved.gfa graph.merged.gfa --all
```

Use `--candidate 0` to export every auto-repeat candidate:

```bash
scripts/gfa_editor_cli.py auto-repeat graph.gfa graph.resolved.gfa --candidate 0
```

This writes files such as `graph.resolved.auto_repeat_001.gfa`, `graph.resolved.auto_repeat_002.gfa`, and later candidates. Candidate numbers are deterministic for the same input and are ordered by the head-to-tail continuous sequence features of the candidate after merging.

Run both steps in one command:

```bash
scripts/gfa_editor_cli.py auto-merge graph.gfa graph.merged.gfa --resolved-output graph.resolved.gfa
```

For another sample with multiple candidate resolutions, choose the candidate whose merged sequence is most continuously similar to a reference merged graph:

```bash
scripts/gfa_editor_cli.py auto-merge graph2.gfa graph2.merged.gfa --reference-merged graph.merged.gfa --resolved-output graph2.resolved.gfa
```

The same reference-guided selection can use FASTA directly:

```bash
scripts/gfa_editor_cli.py auto-repeat graph2.gfa graph2.resolved.gfa --reference-fasta reference.fa
scripts/gfa_editor_cli.py auto-merge graph2.gfa graph2.merged.gfa --reference-fasta reference.fa --resolved-output graph2.resolved.gfa
```

The selector compares each candidate after merge, prefers exact circular sequence matches, and otherwise scores long continuous collinear k-mer chains. Multi-record FASTA files are supported by choosing the best-matching record for each candidate. Passing `--candidate N` still forces that candidate explicitly.

Other CLI commands mirror common toolbar actions, including `stats`, `export`, `delete`, `duplicate`, `repeat`, `rotate`, `update-node`, and `update-edge`.
Use `scripts/gfa_editor_cli.py --version` to print the CLI version.

The macOS standalone app exposes the same CLI through its bundle executable:

```bash
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor auto-repeat graph.gfa graph.resolved.gfa --candidate 0
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor --version
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor auto-merge graph.gfa graph.merged.gfa --candidate 2 --resolved-output graph.resolved.gfa
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor auto-repeat graph.gfa graph.resolved.gfa --reference-fasta reference.fa
/Applications/GFA_Editor.app/Contents/MacOS/GFA_Editor image graph.gfa graph.pdf --colour blastsolid --query multi_fasta.fa --alignment-tool minimap2 --alignment-args "-x asm5 -c --secondary=yes"
```

Running the app without command-line arguments still opens the desktop GUI.

## 11. Desktop and Standalone Builds

Build the macOS app:

```bash
scripts/setup_local_dev.sh --desktop
scripts/build_desktop_app.sh
```

Output:

```text
dist/GFA_Editor.app
```

Build the Windows executable on Windows 11 x86_64:

```powershell
scripts\build_windows_exe.ps1
```

Output:

```text
dist\GFA_Editor\GFA_Editor.exe
```

When distributing the Windows build, share the whole `dist\GFA_Editor` folder because it contains the runtime, frontend files, example data, and packaged alignment tools.

The app icon source file is:

```text
packaging/icons/GFA_Editor_source.png
```

Regenerate icons:

```bash
python scripts/generate_app_icons.py
```

The script generates the frontend PNG, macOS `.icns`, Windows `.ico`, and iconset PNG files.

## 12. Troubleshooting

If the port is already in use, first try:

```bash
scripts/stop_local.sh
```

If the port is used by another process:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
kill <PID>
```

If alignment fails, check whether `minimap2` or `blastn` is installed, or whether the tools were collected into:

```text
packaging/bin/<platform>/
```

If the desktop app does not open an embedded window and falls back to browser mode, check the log:

```text
~/GFAEditorData/desktop.log
```

Unsigned local macOS builds may require right-clicking Open or clearing quarantine:

```bash
scripts/macos_clear_quarantine.sh dist/GFA_Editor.app
```
