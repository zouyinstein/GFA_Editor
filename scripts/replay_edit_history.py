from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.edit_history import apply_edit_history
from backend.gfa_core import export_gfa, parse_gfa_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay a GFA edit-history JSON file.")
    parser.add_argument("input_gfa", type=Path, help="Original input GFA")
    parser.add_argument("history_json", type=Path, help="Edit history JSON")
    parser.add_argument("output_gfa", type=Path, help="Rendered edited GFA")
    parser.add_argument(
        "--no-keep-sequences",
        action="store_true",
        help="Drop input sequences while replaying edits",
    )
    args = parser.parse_args()

    graph = parse_gfa_text(
        args.input_gfa.read_text(encoding="utf-8", errors="replace"),
        keep_sequences=not args.no_keep_sequences,
    )
    history = json.loads(args.history_json.read_text(encoding="utf-8", errors="replace"))
    result = apply_edit_history(graph, history)
    args.output_gfa.write_text(export_gfa(graph), encoding="utf-8")
    print(f"replayed steps={result['step_count']} output={args.output_gfa}")


if __name__ == "__main__":
    main()
