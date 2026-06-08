from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.gfa_core import delete_edge, delete_node, duplicate_node, export_gfa, parse_gfa_text


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the GFA parser/editor core.")
    parser.add_argument("gfa", type=Path, help="Input GFA path")
    args = parser.parse_args()

    text = args.gfa.read_text(encoding="utf-8", errors="replace")
    graph = parse_gfa_text(text, keep_sequences=False)
    stats = graph.stats()
    print(f"loaded nodes={stats['node_count']} edges={stats['edge_count']} bp={stats['total_bp']}")

    if graph.links:
        deleted_edge = graph.links[0].id
        delete_edge(graph, deleted_edge)
        print(f"delete_edge id={deleted_edge} edges={len(graph.links)}")

    first_node = next(iter(graph.segments), None)
    if first_node:
        result = duplicate_node(graph, first_node)
        print(
            "duplicate_node "
            f"source={result['source_node_id']} copy={result['new_node_id']} "
            f"copied_edges={result['copied_edges']}"
        )
        delete_node(graph, result["new_node_id"])
        print(f"delete_node id={result['new_node_id']} nodes={len(graph.segments)} edges={len(graph.links)}")

    exported = export_gfa(graph)
    print(f"exported_lines={len(exported.splitlines())}")


if __name__ == "__main__":
    main()
