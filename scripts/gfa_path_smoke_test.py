from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.gfa_core import delete_node, parse_gfa_text, update_node


GFA_TEXT = """H\tVN:Z:1.0
S\tleft_a\tAAAA\tLN:i:4
S\tleft_b\tCCCC\tLN:i:4
S\trepeat\tGGGG\tLN:i:4\tNC:Z:repeat_node
S\tright_a\tTTTT\tLN:i:4
S\tright_b\tACAC\tLN:i:4
L\tleft_a\t+\trepeat\t+\t0M
L\tleft_b\t+\trepeat\t+\t0M
L\trepeat\t+\tright_a\t+\t0M
L\trepeat\t+\tright_b\t+\t0M
P\trepeat_repeat_p1\tleft_a+,repeat+,right_a+\t*,*\tPT:Z:repeat_path_support\tRN:Z:repeat\tPI:Z:p1\tRC:f:10.000\tPR:f:0.250000\tLE:Z:left_a+\tRE:Z:right_a+
P\trepeat_repeat_p2\tleft_a+,repeat+,right_b+\t*,*\tPT:Z:repeat_path_support\tRN:Z:repeat\tPI:Z:p2\tRC:f:20.000\tPR:f:0.500000\tLE:Z:left_a+\tRE:Z:right_b+
P\trepeat_repeat_p3\tleft_b+,repeat+,right_a+\t*,*\tPT:Z:repeat_path_support\tRN:Z:repeat\tPI:Z:p3\tRC:f:5.000\tPR:f:0.125000\tLE:Z:left_b+\tRE:Z:right_a+
P\trepeat_repeat_p4\tleft_b+,repeat+,right_b+\t*,*\tPT:Z:repeat_path_support\tRN:Z:repeat\tPI:Z:p4\tRC:f:5.000\tPR:f:0.125000\tLE:Z:left_b+\tRE:Z:right_b+
"""


def main() -> None:
    graph = parse_gfa_text(GFA_TEXT, keep_sequences=False)
    assert graph.stats()["path_count"] == 4

    payload = graph.to_client()
    repeat_node = next(node["data"] for node in payload["nodes"] if node["data"]["id"] == "repeat")
    assert repeat_node["isRepeatNode"] is True
    assert repeat_node["gfaPathCount"] == 4
    assert [path["pathIndex"] for path in repeat_node["gfaPaths"]] == ["p1", "p2", "p3", "p4"]
    assert repeat_node["gfaPaths"][1]["supportCount"] == 20.0

    update_node(graph, "repeat", name="repeat_renamed")
    renamed = next(node["data"] for node in graph.to_client()["nodes"] if node["data"]["id"] == "repeat_renamed")
    assert renamed["gfaPathCount"] == 4
    assert all(path["repeatNodeId"] == "repeat_renamed" for path in renamed["gfaPaths"])
    assert all(path["steps"][1]["node"] == "repeat_renamed" for path in renamed["gfaPaths"])

    delete_node(graph, "repeat_renamed")
    assert graph.stats()["path_count"] == 0
    print("gfa_path smoke ok")


if __name__ == "__main__":
    main()
