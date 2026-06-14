# GFA Editor 1.2.8 Implementation Notes

This file records the public engineering notes for the CLI repeat-resolution work. It is a concise design and verification summary, not a private chain-of-thought transcript.

## Scope

- Added command-line graph rendering with Bandage-style `image` usage, including `--colour blastsolid --query`.
- Added command-line repeat-resolution workflows: `auto-repeat`, `merge`, and `auto-merge`.
- Added support for exporting every auto-repeat candidate with `--candidate 0`.
- Added reference-guided `auto-merge` selection for second samples with multiple candidate resolutions.

## Candidate Numbering

- Candidate IDs are normalized as `auto_repeat_001`, `auto_repeat_002`, and so on.
- Candidate order is deterministic for the same input.
- Numbering is based on head-to-tail continuous sequence features after each candidate is merged, so a candidate number represents the merged arrangement rather than the incidental search order.

## Reference-Guided Selection

- `auto-merge --reference-merged reference.gfa` merges each auto-repeat candidate and compares the resulting single sequence with the reference merged graph.
- Exact circular sequence matches are preferred and receive score `1.0`.
- Otherwise, candidates are scored by long continuous collinear k-mer chains against the reference merged sequence, checking both forward and reverse-complement orientations.
- A manual `--candidate N` still overrides reference-guided selection.

## Verification

- `python3 -m py_compile backend/cli.py backend/graph_ops.py scripts/cli_smoke_test.py`
- `python3 scripts/cli_smoke_test.py`
- `python3 scripts/merge_selection_smoke_test.py`
- `.venv/bin/python scripts/api_smoke_test.py examples/mecat_mito_500K_before_rr.gfa`
- Real wheat reference regression selected `auto_repeat_013` with `score=1`, `method=sequence-exact-circular`; the merged sequence matched the reference sequence exactly at length `455027`.
- Repeated `--candidate 0` runs on the wheat graph produced 100 candidate files with stable candidate numbering and byte-identical outputs for matching candidate IDs.

## 1.2.8 App CLI Mode

- The macOS standalone app now supports CLI dispatch from its bundle executable.
- Running `GFA_Editor.app/Contents/MacOS/GFA_Editor` with CLI arguments forwards those arguments to `backend.cli.main`.
- Running the app without CLI arguments, or with only the Finder `-psn_...` launch argument, still opens the desktop GUI.
- CLI mode preserves the caller's current working directory so relative input and output paths behave like `scripts/gfa_editor_cli.py`.
