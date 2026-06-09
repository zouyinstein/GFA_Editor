# Bundled Alignment Tools

This directory is used by local and desktop packaging scripts.

Expected layout:

```text
packaging/bin/
  macos-arm64/
    minimap2
    blastn
  macos-x86_64/
  linux-x86_64/
  linux-arm64/
  windows-x86_64/
```

Run this from the project root to copy tools available on the current machine:

```bash
scripts/collect_alignment_tools.sh
```

`minimap2` is usually easy to bundle as a single executable. `blastn` often depends on shared libraries from the BLAST installation, so each release package should be tested on a clean machine.
