from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.gfa_core import merge_selection, parse_gfa_text


def tiny_chain(extra_lines: str = ""):
    text = (
        "H\tVN:Z:1.0\n"
        "S\tA\tAAA\n"
        "S\tB\tCCC\n"
        "S\tC\tGGG\n"
        "S\tD\tTTT\n"
        "L\tA\t+\tB\t+\t0M\n"
        "L\tB\t+\tC\t+\t0M\n"
        f"{extra_lines}"
    )
    return parse_gfa_text(text, keep_sequences=True)


def expect_value_error(callback) -> None:
    try:
        callback()
    except ValueError:
        return
    raise AssertionError("Expected ValueError")


def main() -> None:
    graph = tiny_chain()
    result = merge_selection(graph, ["A", "B", "C"], [])
    assert result["path_node_ids"] == ["A", "B", "C"]
    assert result["new_node_id"] == "A_B_C"
    assert list(graph.segments) == ["A_B_C", "D"]
    assert graph.segments["A_B_C"].sequence == "AAACCCGGG"
    assert len(graph.links) == 0

    graph = tiny_chain()
    result = merge_selection(graph, ["A", "B"], [graph.links[0].id])
    assert result["path_node_ids"] == ["A", "B"]
    assert result["new_node_id"] == "A_B"
    assert graph.segments["A_B"].sequence == "AAACCC"

    graph = tiny_chain()
    result = merge_selection(graph, [], [graph.links[0].id])
    assert result["new_node_id"] == "A_B"

    graph = tiny_chain("L\tC\t+\tA\t+\t0M\n")
    internal_edge_ids = [
        link.id
        for link in graph.links
        if link.source in {"A", "B", "C"} and link.target in {"A", "B", "C"}
    ]
    result = merge_selection(graph, ["A", "B", "C"], internal_edge_ids)
    assert result["new_node_id"] == "A_B_C"
    assert result["retained_cycle_edge_ids"]
    assert graph.segments["A_B_C"].sequence == "AAACCCGGG"
    assert len(graph.links) == 1
    assert graph.links[0].source == "A_B_C"
    assert graph.links[0].target == "A_B_C"

    graph = tiny_chain("L\tA\t+\tD\t+\t0M\n")
    result = merge_selection(graph, ["A", "B", "C"], [])
    assert result["new_node_id"] == "A_B_C"
    assert len(graph.links) == 1
    assert {graph.links[0].source, graph.links[0].target} == {"A_B_C", "D"}

    graph = tiny_chain("L\tA\t+\tB\t-\t0M\n")
    expect_value_error(lambda: merge_selection(graph, ["A", "B"], []))

    graph = tiny_chain("L\tA\t-\tC\t-\t0M\n")
    result = merge_selection(graph, ["A", "B", "C"], [])
    assert result["retained_cycle_edge_ids"]

    graph = tiny_chain("L\tB\t-\tD\t+\t0M\n")
    expect_value_error(lambda: merge_selection(graph, ["A", "B", "C"], []))

    same_side_text = (
        "H\tVN:Z:1.0\n"
        "S\tA\tAAA\n"
        "S\tB\tCCC\n"
        "S\tC\tGGG\n"
        "L\tA\t+\tB\t+\t0M\n"
        "L\tB\t-\tC\t+\t0M\n"
    )
    graph = parse_gfa_text(same_side_text, keep_sequences=True)
    expect_value_error(lambda: merge_selection(graph, ["A", "B", "C"], []))

    graph = tiny_chain("L\tA\t-\tD\t+\t0M\n")
    expect_value_error(lambda: merge_selection(graph, ["A", "B", "C"], [graph.links[-1].id]))

    two_node_cycle_text = (
        "H\tVN:Z:1.0\n"
        "S\tA\tAAA\n"
        "S\tB\tCCC\n"
        "L\tA\t+\tB\t+\t0M\n"
        "L\tB\t+\tA\t+\t0M\n"
    )
    graph = parse_gfa_text(two_node_cycle_text, keep_sequences=True)
    result = merge_selection(graph, ["A", "B"], [])
    assert result["path_node_ids"] == ["A", "B"]
    assert result["retained_cycle_edge_ids"]
    assert graph.segments["A_B"].sequence == "AAACCC"
    assert len(graph.links) == 1
    assert graph.links[0].source == "A_B"
    assert graph.links[0].target == "A_B"

    graph = parse_gfa_text(two_node_cycle_text, keep_sequences=True)
    result = merge_selection(graph, [], [link.id for link in graph.links])
    assert result["new_node_id"] == "A_B"
    assert result["retained_cycle_edge_ids"]
    assert len(graph.links) == 1
    assert graph.links[0].source == "A_B"
    assert graph.links[0].target == "A_B"

    print("merge_selection smoke ok")


if __name__ == "__main__":
    main()
