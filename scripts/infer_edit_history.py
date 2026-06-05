from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.edit_history import infer_edit_history
from backend.gfa_core import parse_gfa_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Infer a pseudo GFA edit-history JSON file.")
    parser.add_argument("old_gfa", type=Path, help="Original GFA")
    parser.add_argument("new_gfa", type=Path, help="Edited GFA")
    parser.add_argument("output_history_json", type=Path, help="Output history JSON")
    parser.add_argument(
        "--no-keep-sequences",
        action="store_true",
        help="Drop sequences while comparing GFAs",
    )
    args = parser.parse_args()

    keep_sequences = not args.no_keep_sequences
    old_graph = parse_gfa_text(
        args.old_gfa.read_text(encoding="utf-8", errors="replace"),
        keep_sequences=keep_sequences,
    )
    new_graph = parse_gfa_text(
        args.new_gfa.read_text(encoding="utf-8", errors="replace"),
        keep_sequences=keep_sequences,
    )
    history = infer_edit_history(old_graph, new_graph, source_name=args.old_gfa.name)
    args.output_history_json.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    print(
        "inferred "
        f"steps={len(history['steps'])} "
        f"warnings={len(history['warnings'])} "
        f"output={args.output_history_json}"
    )


if __name__ == "__main__":
    main()
