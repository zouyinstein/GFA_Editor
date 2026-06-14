# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .edit_history import history_step_from_event
from .gfa_core import GfaGraph, deduplicate_links, duplicate_node, merge_selection, repeat_resolve_node


@dataclass
class AutoRepeatCandidate:
    id: str
    graph: GfaGraph
    steps: List[Dict[str, Any]]
    order: List[Dict[str, Any]]
    signature: str
    circular: bool
    merged_order_count: int = 1

    def summary(self) -> Dict[str, Any]:
        node_count = len(self.graph.segments)
        link_count = len(self.graph.links)
        return {
            "id": self.id,
            "label": f"Result {self.id.rsplit('_', 1)[-1]}: {node_count} nodes, {link_count} links, {len(self.steps)} steps",
            "nodeCount": node_count,
            "linkCount": link_count,
            "stepCount": len(self.steps),
            "resolvedNodeCount": len(self.order),
            "order": copy.deepcopy(self.order),
            "circular": self.circular,
            "mergedOrderCount": self.merged_order_count,
        }


def normalize_candidate_ids(candidates: List[AutoRepeatCandidate]) -> List[AutoRepeatCandidate]:
    for index, candidate in enumerate(candidates, start=1):
        candidate.id = f"auto_repeat_{index:03d}"
    return candidates


def order_candidates_by_merged_sequence_features(candidates: List[AutoRepeatCandidate]) -> List[AutoRepeatCandidate]:
    indexed_candidates = list(enumerate(candidates))
    indexed_candidates.sort(key=lambda item: merged_sequence_feature_key(item[1], item[0]))
    return [candidate for _, candidate in indexed_candidates]


def merged_sequence_feature_key(candidate: AutoRepeatCandidate, original_index: int) -> Tuple[Any, ...]:
    try:
        merged_graph = candidate.graph.clone()
        if len(merged_graph.segments) >= 2:
            merge_selection(merged_graph, list(merged_graph.segments), [])
        deduplicate_links(merged_graph)
        segment = next(iter(merged_graph.segments.values()), None)
    except (KeyError, ValueError):
        segment = None
    if segment is not None and segment.sequence:
        sequence = segment.sequence.upper()
        return (
            0,
            len(sequence),
            head_to_tail_sequence_feature(sequence),
            candidate.signature,
            original_index,
        )
    if segment is not None:
        return (
            1,
            segment.length,
            head_to_tail_node_id_feature(segment.id),
            candidate.signature,
            original_index,
        )
    return (2, candidate.signature, original_index)


def head_to_tail_sequence_feature(sequence: str) -> Tuple[Any, ...]:
    sequence_length = len(sequence)
    kmer_size = 31 if sequence_length >= 31 else max(1, sequence_length)
    anchor_count = min(256, max(1, sequence_length - kmer_size + 1))
    if anchor_count == 1:
        anchors = [sequence[:kmer_size]]
    else:
        last_position = sequence_length - kmer_size
        anchors = [
            sequence[(index * last_position) // (anchor_count - 1) : (index * last_position) // (anchor_count - 1) + kmer_size]
            for index in range(anchor_count)
        ]
    head = sequence[:256]
    tail = sequence[-256:] if sequence_length > 256 else sequence
    digest = hashlib.sha256(sequence.encode("ascii", errors="ignore")).hexdigest()
    return (kmer_size, tuple(anchors), head, tail, digest)


def head_to_tail_node_id_feature(node_id: str) -> Tuple[str, ...]:
    return tuple(part for part in node_id.split("_") if part)


def endpoint_side(orient: str, role: str) -> str:
    if role == "target":
        return "+" if orient == "-" else "-"
    return "-" if orient == "-" else "+"


def graph_link_key(link: Any) -> Tuple[Any, ...]:
    endpoints = sorted(
        (
            (link.source, endpoint_side(link.source_orient, "source")),
            (link.target, endpoint_side(link.target_orient, "target")),
        )
    )
    tags = tuple(
        sorted(
            (
                tag,
                str(payload.get("type", "")),
                str(payload.get("raw", payload.get("value", ""))),
            )
            for tag, payload in link.tags.items()
        )
    )
    return (
        tuple(endpoints),
        link.cigar,
        link.support,
        tags,
    )


def graph_topology_signature(graph: GfaGraph) -> str:
    nodes = [
        (
            node_id,
            segment.length,
            segment.depth,
            tuple(
                sorted(
                    (
                        tag,
                        str(payload.get("type", "")),
                        str(payload.get("raw", payload.get("value", ""))),
                    )
                    for tag, payload in segment.tags.items()
                )
            ),
        )
        for node_id, segment in sorted(graph.segments.items())
    ]
    links = sorted(graph_link_key(link) for link in graph.links)
    return json.dumps({"nodes": nodes, "links": links}, sort_keys=True, separators=(",", ":"))


def valid_graph_links(graph: GfaGraph) -> List[Any]:
    return [
        link
        for link in unique_links_by_topology(graph.links)
        if link.source in graph.segments and link.target in graph.segments
    ]


def unique_links_by_topology(links: List[Any]) -> List[Any]:
    seen = set()
    unique = []
    for link in links:
        key = graph_link_key(link)
        if key in seen:
            continue
        seen.add(key)
        unique.append(link)
    return unique


def graph_is_connected(graph: GfaGraph) -> bool:
    node_ids = list(graph.segments)
    if not node_ids:
        return False
    if len(node_ids) == 1:
        return True
    adjacency = {node_id: set() for node_id in node_ids}
    for link in valid_graph_links(graph):
        if link.source == link.target:
            continue
        adjacency[link.source].add(link.target)
        adjacency[link.target].add(link.source)
    seen = {node_ids[0]}
    pending = [node_ids[0]]
    while pending:
        node_id = pending.pop()
        for neighbor_id in adjacency[node_id]:
            if neighbor_id in seen:
                continue
            seen.add(neighbor_id)
            pending.append(neighbor_id)
    return len(seen) == len(node_ids)


def node_side_counts(graph: GfaGraph, node_id: str) -> Tuple[Dict[str, int], bool]:
    counts = {"-": 0, "+": 0}
    has_self_loop = False
    for link in valid_graph_links(graph):
        if link.source == node_id and link.target == node_id:
            has_self_loop = True
            continue
        if link.source == node_id:
            counts[endpoint_side(link.source_orient, "source")] += 1
        if link.target == node_id:
            counts[endpoint_side(link.target_orient, "target")] += 1
    return counts, has_self_loop


def auto_repeat_ready_node_ids(graph: GfaGraph) -> List[str]:
    ready = []
    for node_id in graph.segments:
        counts, has_self_loop = node_side_counts(graph, node_id)
        if not has_self_loop and counts["-"] == 2 and counts["+"] == 2:
            ready.append(node_id)
    return ready


def graph_is_circular_subgraph(graph: GfaGraph) -> bool:
    if not graph_is_connected(graph):
        return False
    if len(valid_graph_links(graph)) != len(graph.segments):
        return False
    for node_id in graph.segments:
        counts, has_self_loop = node_side_counts(graph, node_id)
        if has_self_loop or counts["-"] != 1 or counts["+"] != 1:
            return False
    return True


def build_auto_repeat_resolution_candidates(
    graph: GfaGraph,
    *,
    max_states: int,
    max_candidates: int,
) -> Tuple[List[AutoRepeatCandidate], Optional[str]]:
    if not graph_is_connected(graph):
        raise ValueError("Auto repeat resolution requires the selected subgraph to be connected")
    targets = tuple(sorted(auto_repeat_ready_node_ids(graph)))
    if not targets:
        return [], "No 2-in/2-out repeat nodes were found in the selected subgraph."

    states = [
        {
            "graph": graph.clone(),
            "remaining": targets,
            "steps": [],
            "order": [],
        }
    ]
    visited = set()
    final_by_signature: Dict[str, AutoRepeatCandidate] = {}
    explored_state_count = 0
    truncated = False

    while states:
        state = states.pop()
        state_graph: GfaGraph = state["graph"]
        remaining = tuple(sorted(state["remaining"]))
        state_key = (remaining, graph_topology_signature(state_graph))
        if state_key in visited:
            continue
        visited.add(state_key)
        explored_state_count += 1
        if explored_state_count > max_states:
            truncated = True
            break

        if not remaining:
            final_signature = graph_topology_signature(state_graph)
            existing = final_by_signature.get(final_signature)
            if existing is not None:
                existing.merged_order_count += 1
                continue
            candidate_index = len(final_by_signature) + 1
            candidate_id = f"auto_repeat_{candidate_index:03d}"
            final_by_signature[final_signature] = AutoRepeatCandidate(
                id=candidate_id,
                graph=state_graph.clone(),
                steps=copy.deepcopy(state["steps"]),
                order=copy.deepcopy(state["order"]),
                signature=final_signature,
                circular=graph_is_circular_subgraph(state_graph),
            )
            if len(final_by_signature) >= max_candidates:
                truncated = bool(states)
                break
            continue

        for node_id in remaining:
            counts, has_self_loop = node_side_counts(state_graph, node_id)
            if has_self_loop or counts["-"] != 2 or counts["+"] != 2:
                continue
            for strategy in ("A", "B"):
                next_graph = state_graph.clone()
                try:
                    duplicate_result = duplicate_node(next_graph, node_id)
                    duplicate_id = duplicate_result["new_node_id"]
                    repeat_result = repeat_resolve_node(next_graph, node_id, duplicate_id, strategy)
                    deduplicate_links(next_graph)
                except (KeyError, ValueError):
                    continue
                if not graph_is_connected(next_graph):
                    continue

                duplicate_details = {"node_id": node_id, **duplicate_result}
                duplicate_step = history_step_from_event("duplicate_node", duplicate_details)
                repeat_details = {
                    "node_id": node_id,
                    "duplicate_id": duplicate_id,
                    "strategy": strategy,
                    **repeat_result,
                }
                repeat_step = history_step_from_event("repeat_resolution", repeat_details)
                if duplicate_step is None or repeat_step is None:
                    continue
                next_remaining = tuple(candidate for candidate in remaining if candidate != node_id)
                states.append(
                    {
                        "graph": next_graph,
                        "remaining": next_remaining,
                        "steps": [
                            *copy.deepcopy(state["steps"]),
                            duplicate_step,
                            repeat_step,
                        ],
                        "order": [
                            *copy.deepcopy(state["order"]),
                            {
                                "nodeId": node_id,
                                "duplicateId": duplicate_id,
                                "strategy": strategy,
                            },
                        ],
                    }
                )

    candidates = normalize_candidate_ids(order_candidates_by_merged_sequence_features(list(final_by_signature.values())))
    warning = None
    if truncated:
        warning = (
            f"Search stopped after {explored_state_count} states. "
            f"Showing {len(candidates)} unique candidate results."
        )
    elif not candidates:
        warning = "No connected result could resolve all 2-in/2-out repeat nodes."
    return candidates, warning
