from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.gfa_core import delete_selection, parse_gfa_text
from backend.main import EditorSession


GFA_TEXT = """H\tVN:Z:1.0
S\ta\tACGTACGTACGT\tLN:i:12
S\tb\tTTTTCCCCAAAA\tLN:i:12
S\tc\tGGGGAAAACCCC\tLN:i:12
L\ta\t+\tb\t+\t0M
L\tb\t+\tc\t+\t0M
"""


def node_ids(session: EditorSession) -> set[str]:
    assert session.graph is not None
    return set(session.graph.segments)


def main() -> None:
    session = EditorSession()
    session.load(parse_gfa_text(GFA_TEXT, keep_sequences=True), "tiny.gfa")
    upload_state = session.log[-1]["state_index"]

    session.apply_alignment({"q1": []}, format="paf", target_role="subject", source_name="q.paf")
    alignment_state = session.log[-1]["state_index"]

    session.mutate(
        "delete_selection",
        {"node_ids": ["a", "b"], "edge_ids": []},
        lambda graph: delete_selection(graph, ["a", "b"], []),
    )
    delete_state = session.log[-1]["state_index"]
    assert node_ids(session) == {"c"}

    session.undo()
    assert node_ids(session) == {"a", "b", "c"}
    assert session.alignment_source_name == "q.paf"
    assert session.active_operation_state_index == alignment_state

    session.redo()
    assert node_ids(session) == {"c"}
    assert session.active_operation_state_index == delete_state

    session.restore_operation_state(upload_state)
    assert node_ids(session) == {"a", "b", "c"}
    assert session.alignment_source_name is None
    assert session.active_operation_state_index == upload_state

    session.redo()
    assert session.alignment_source_name == "q.paf"
    assert session.active_operation_state_index == alignment_state

    session.restore_operation_state(alignment_state)
    assert node_ids(session) == {"a", "b", "c"}
    assert session.alignment_source_name == "q.paf"
    assert session.active_operation_state_index == alignment_state

    session.redo()
    assert node_ids(session) == {"c"}
    assert session.active_operation_state_index == delete_state

    session.restore_operation_state(delete_state)
    session.undo()
    assert node_ids(session) == {"a", "b", "c"}
    assert session.alignment_source_name == "q.paf"
    assert session.active_operation_state_index == alignment_state

    print("operation_state smoke ok")


if __name__ == "__main__":
    main()
