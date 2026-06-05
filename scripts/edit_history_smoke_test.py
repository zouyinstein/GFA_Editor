from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.edit_history import (
    apply_edit_history,
    build_history_document,
    history_step_from_event,
    infer_edit_history,
)
from backend.gfa_core import export_gfa, merge_selection, parse_gfa_text, rotate_circular_node


RING_GFA = (
    "H\tVN:Z:1.0\n"
    "S\tA\tAAC\n"
    "S\tB\tCCG\n"
    "S\tC\tGGT\n"
    "L\tA\t+\tB\t+\t0M\n"
    "L\tB\t+\tC\t+\t0M\n"
    "L\tC\t+\tA\t+\t0M\n"
)


def make_ring():
    return parse_gfa_text(RING_GFA, keep_sequences=True)


def main() -> None:
    edited = make_ring()
    merge_result = merge_selection(edited, ["A", "B", "C"], [])
    merged_id = merge_result["new_node_id"]
    rotate_result = rotate_circular_node(edited, merged_id, 2)
    assert edited.segments[merged_id].sequence == "CCCGGGTAA"
    assert len(edited.links) == 1
    assert edited.links[0].source == merged_id and edited.links[0].target == merged_id

    history = build_history_document(
        [
            history_step_from_event("merge_selection", merge_result),
            history_step_from_event("rotate_circular_node", rotate_result),
        ],
        source_name="ring.gfa",
    )

    replayed = make_ring()
    apply_result = apply_edit_history(replayed, history)
    assert apply_result["step_count"] == 2
    assert export_gfa(replayed) == export_gfa(edited)

    inferred = infer_edit_history(make_ring(), edited, source_name="ring.gfa")
    assert [step["action"] for step in inferred["steps"]] == [
        "merge_selection",
        "rotate_circular_node",
    ]

    replayed_inferred = make_ring()
    apply_edit_history(replayed_inferred, inferred)
    assert export_gfa(replayed_inferred) == export_gfa(edited)

    print(
        "edit_history smoke ok "
        f"steps={len(history['steps'])} "
        f"inferred_warnings={len(inferred['warnings'])}"
    )


if __name__ == "__main__":
    main()
