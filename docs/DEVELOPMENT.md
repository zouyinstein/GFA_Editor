# Developer Notes

This file keeps developer-facing notes out of the public README.

## Current Architecture

- Backend: FastAPI in `backend/main.py`.
- Core GFA parsing/editing/alignment logic: `backend/gfa_core.py`.
- Frontend: static HTML/CSS/JS in `frontend/`.
- Local static dependencies are vendored under `frontend/vendor/`.
- The backend serves the frontend directly, so a browser only needs `http://127.0.0.1:8000`.

## Implemented Areas

- Parse common GFA 1.x `H`, `S`, and `L` records.
- Preserve segment sequence optionally for GFA/FASTA export and circular rotation.
- Render Cytoscape views and SVG Bandage-style views, including `Bandage_native`.
- Edit contigs and links, duplicate contigs, delete nodes/links, merge selected paths, rotate circular contig starts.
- Store labels/colors as `LB:Z` and `CL:Z` tags.
- Maintain undo/redo and exportable edit-history JSON.
- Load/save files from a server data directory and transfer files through SFTP.
- Import or run alignments with BLAST outfmt 6 or minimap2 PAF.
- Select individual reads from a multi-read alignment and visualize node/link paths plus partial-contig hit spans.
- Export whole graph or selected links as GFA/FASTA.

## Local Development

```bash
scripts/setup_local_dev.sh
scripts/start_local.sh
```

Use `scripts/stop_local.sh` to stop the background server.

For desktop-wrapper development:

```bash
scripts/setup_local_dev.sh --desktop
scripts/run_desktop.sh
```

## Tests

```bash
.venv/bin/python scripts/smoke_test.py examples/mecat_mito_500K_before_rr.gfa
.venv/bin/python scripts/api_smoke_test.py examples/mecat_mito_500K_before_rr.gfa
.venv/bin/python scripts/merge_selection_smoke_test.py
.venv/bin/python scripts/edit_history_smoke_test.py
node --check frontend/app.js
```

## Packaging

Browser/local package:

```bash
scripts/build_quasi_standalone.sh
```

Desktop app:

```bash
scripts/build_desktop_app.sh
```

PyInstaller builds are platform-specific. Build macOS packages on macOS, Windows packages on Windows, and Linux packages on Linux.

## Future Extension Ideas

- Add backend pagination and subgraph expansion for very large GFAs.
- Support GFA `P` and `W` path records more fully.
- Add a project file format bundling GFA, alignments, edit history, labels, colors, and layout state.
- Improve release packaging for clean-machine BLAST dependencies.
- Add signed/notarized macOS releases and Windows installer metadata once the standalone path stabilizes.
