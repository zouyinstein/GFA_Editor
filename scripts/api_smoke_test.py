from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi.testclient import TestClient

from backend.gfa_core import parse_gfa_text
from backend.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the FastAPI endpoints.")
    parser.add_argument("gfa", type=Path, help="Input GFA path")
    args = parser.parse_args()

    client = TestClient(app)
    with args.gfa.open("rb") as handle:
        response = client.post(
            "/api/upload",
            files={"file": (args.gfa.name, handle, "text/plain")},
            data={"keep_sequences": "false"},
        )
    response.raise_for_status()
    payload = response.json()
    print(
        "upload "
        f"nodes={payload['stats']['node_count']} "
        f"edges={payload['stats']['edge_count']} "
        f"source={payload['session']['source_name']}"
    )

    first_node = payload["nodes"][0]["data"]["id"]
    response = client.get("/api/export?format=fasta")
    response.raise_for_status()
    assert response.text.startswith(">")
    print("fasta_from_light_mode_cache status=200")

    blast_text = (
        f"{first_node}\tref_mito_chr\t99.2\t1200\t4\t0\t1\t1200\t30\t1229\t1e-180\t850\n"
    )
    response = client.post(
        "/api/upload_blast",
        files={"file": ("blast_example.tsv", blast_text, "text/plain")},
    )
    response.raise_for_status()
    payload = response.json()
    latest = payload["session"]["history"][-1]["details"]
    print(
        "blast "
        f"matched={latest['matched_queries']} "
        f"unmatched={latest['unmatched_queries']} "
        f"hits={latest['total_hits']}"
    )

    renamed_node = f"{first_node}_renamed"
    response = client.post(
        "/api/update_node",
        json={
            "node_id": first_node,
            "name": renamed_node,
            "label": "edited contig",
            "color": "#33aa77",
            "depth": 66,
        },
    )
    response.raise_for_status()
    payload = response.json()
    print(
        "update_node "
        f"old={first_node} "
        f"new={renamed_node} "
        f"nodes={payload['stats']['node_count']}"
    )
    first_node = renamed_node

    first_edge = payload["edges"][0]["data"]["id"]
    response = client.post(
        "/api/update_edge",
        json={
            "edge_id": first_edge,
            "label": "edited link",
            "color": "#cc44aa",
            "support": 77,
            "cigar": "0M",
        },
    )
    response.raise_for_status()
    payload = response.json()
    print(f"update_edge edge={first_edge} support=77")

    response = client.post("/api/duplicate_node", json={"node_id": first_node})
    response.raise_for_status()
    payload = response.json()
    print(
        "duplicate "
        f"nodes={payload['stats']['node_count']} "
        f"edges={payload['stats']['edge_count']} "
        f"can_undo={payload['session']['can_undo']}"
    )

    response = client.post("/api/undo")
    response.raise_for_status()
    payload = response.json()
    print(f"undo nodes={payload['stats']['node_count']} edges={payload['stats']['edge_count']}")

    first_edge = payload["edges"][0]["data"]["id"]
    response = client.post("/api/delete_edge", json={"edge_id": first_edge})
    response.raise_for_status()
    payload = response.json()
    print(f"delete_edge edges={payload['stats']['edge_count']}")

    response = client.get("/api/export")
    response.raise_for_status()
    exported = response.text
    print(f"export lines={len(exported.splitlines())} bytes={len(exported.encode('utf-8'))}")

    assert "CL:Z:#33aa77" in exported
    assert "LB:Z:edited contig" in exported

    response = client.get("/api/export_history")
    response.raise_for_status()
    edit_history = response.json()
    assert len(edit_history["steps"]) >= 3
    print(
        "export_history "
        f"steps={len(edit_history['steps'])} "
        f"warnings={len(edit_history['warnings'])}"
    )

    with args.gfa.open("rb") as handle:
        response = client.post(
            "/api/render_history",
            files={
                "gfa_file": (args.gfa.name, handle, "text/plain"),
                "history_file": ("history.json", json.dumps(edit_history), "application/json"),
            },
            data={"keep_sequences": "false"},
    )
    response.raise_for_status()
    rendered = response.text
    rendered_graph = parse_gfa_text(rendered, keep_sequences=False)
    exported_graph = parse_gfa_text(exported, keep_sequences=False)
    assert rendered_graph.stats()["node_count"] == exported_graph.stats()["node_count"]
    assert rendered_graph.stats()["edge_count"] == exported_graph.stats()["edge_count"]
    assert "CL:Z:#33aa77" in rendered
    assert "LB:Z:edited contig" in rendered
    print(f"render_history bytes={len(response.text.encode('utf-8'))}")

    response = client.post("/api/jump_edit_step", json={"target_step_count": 1})
    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["edit_step_count"] == 1
    response = client.post("/api/jump_edit_step", json={"target_step_count": 3})
    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["edit_step_count"] == 3
    response = client.get("/api/export")
    response.raise_for_status()
    assert response.text == exported
    print("jump_edit_step ok")

    with args.gfa.open("rb") as handle:
        response = client.post(
            "/api/upload",
            files={"file": (args.gfa.name, handle, "text/plain")},
            data={"keep_sequences": "false"},
        )
    response.raise_for_status()
    response = client.post(
        "/api/apply_history",
        files={"history_file": ("history.json", json.dumps(edit_history), "application/json")},
    )
    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["history_trace_index"] == len(edit_history["steps"])
    assert len(payload["session"]["history_trace"]) == len(edit_history["steps"]) + 1
    response = client.get("/api/export")
    response.raise_for_status()
    assert response.text == exported
    print(f"apply_history trace_steps={len(payload['session']['history_trace'])}")

    response = client.post("/api/history_trace_step", json={"trace_index": 1})
    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["history_trace_index"] == 1
    response = client.post("/api/history_trace_step", json={"trace_index": len(edit_history["steps"])})
    response.raise_for_status()
    payload = response.json()
    assert payload["session"]["history_trace_index"] == len(edit_history["steps"])
    print("history_trace_step ok")

    with args.gfa.open("rb") as handle:
        response = client.post(
            "/api/upload",
            files={"file": (args.gfa.name, handle, "text/plain")},
            data={"keep_sequences": "true"},
        )
    response.raise_for_status()
    response = client.get("/api/export?format=fasta")
    response.raise_for_status()
    fasta = response.text
    print(f"export_fasta records={fasta.count('>')} bytes={len(fasta.encode('utf-8'))}")


if __name__ == "__main__":
    main()
