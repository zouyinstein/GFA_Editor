from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set

from .gfa_core import (
    GfaGraph,
    delete_edge,
    delete_node,
    duplicate_node,
    merge_link,
    merge_selection,
    repeat_resolve_node,
    rotate_circular_node,
    update_edge,
    update_node,
)


HISTORY_SCHEMA = "gfa-editor-edit-history"
HISTORY_VERSION = 1


def build_history_document(
    steps: Iterable[Dict[str, Any]],
    source_name: Optional[str] = None,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "schema": HISTORY_SCHEMA,
        "version": HISTORY_VERSION,
        "source_name": source_name,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "steps": copy.deepcopy(list(steps)),
        "warnings": warnings or [],
    }


def history_step_from_event(action: str, details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    params: Dict[str, Any]
    if action == "delete_node":
        params = {"node_id": details.get("node_id")}
    elif action == "delete_edge":
        params = {"edge_id": details.get("edge_id")}
    elif action == "duplicate_node":
        params = {
            "node_id": details.get("source_node_id") or details.get("node_id"),
            "new_id": details.get("new_node_id") or details.get("requested_id"),
        }
    elif action == "update_node":
        params = {
            "node_id": details.get("old_node_id") or details.get("node_id"),
            "name": details.get("new_node_id") or details.get("name"),
            "label": details.get("label"),
            "color": details.get("color"),
            "depth": details.get("depth"),
        }
    elif action == "update_edge":
        params = {
            "edge_id": details.get("edge_id"),
            "label": details.get("label"),
            "color": details.get("color"),
            "support": details.get("support"),
            "cigar": details.get("cigar"),
        }
    elif action == "merge_link":
        params = {"edge_id": details.get("edge_id")}
    elif action == "merge_selection":
        params = {
            "node_ids": details.get("node_ids") or details.get("path_node_ids") or [],
            "edge_ids": details.get("edge_ids") or [],
        }
    elif action == "repeat_resolution":
        params = {
            "node_id": details.get("node_id"),
            "duplicate_id": details.get("duplicate_id"),
            "strategy": details.get("strategy"),
        }
    elif action == "rotate_circular_node":
        params = {
            "node_id": details.get("node_id"),
            "offset": details.get("offset"),
        }
    else:
        return None

    cleaned_params = {key: value for key, value in params.items() if value is not None}
    return {
        "action": action,
        "params": cleaned_params,
        "result": copy.deepcopy(details),
    }


def apply_edit_history(graph: GfaGraph, history: Dict[str, Any]) -> Dict[str, Any]:
    steps = history.get("steps")
    if not isinstance(steps, list):
        raise ValueError("History file must contain a steps list")

    applied: List[Dict[str, Any]] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            raise ValueError(f"History step {index + 1} must be an object")
        action = step.get("action")
        params = step.get("params") or {}
        if not isinstance(params, dict):
            raise ValueError(f"History step {index + 1} params must be an object")
        result = _apply_history_step(graph, str(action), params)
        applied.append({"action": action, "params": copy.deepcopy(params), "result": result})
    return {"applied_steps": applied, "step_count": len(applied)}


def _apply_history_step(graph: GfaGraph, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if action == "delete_node":
        return delete_node(graph, str(params["node_id"]))
    if action == "delete_edge":
        return delete_edge(graph, str(params["edge_id"]))
    if action == "duplicate_node":
        return duplicate_node(graph, str(params["node_id"]), params.get("new_id"))
    if action == "update_node":
        return update_node(
            graph,
            str(params["node_id"]),
            name=params.get("name"),
            label=params.get("label"),
            color=params.get("color"),
            depth=params.get("depth"),
        )
    if action == "update_edge":
        return update_edge(
            graph,
            str(params["edge_id"]),
            label=params.get("label"),
            color=params.get("color"),
            support=params.get("support"),
            cigar=params.get("cigar"),
        )
    if action == "merge_link":
        return merge_link(graph, str(params["edge_id"]))
    if action == "merge_selection":
        return merge_selection(graph, params.get("node_ids") or [], params.get("edge_ids") or [])
    if action == "repeat_resolution":
        return repeat_resolve_node(
            graph,
            str(params["node_id"]),
            str(params["duplicate_id"]),
            str(params["strategy"]),
        )
    if action == "rotate_circular_node":
        return rotate_circular_node(graph, str(params["node_id"]), int(params["offset"]))
    raise ValueError(f"Unsupported history action: {action}")


def infer_edit_history(original: GfaGraph, edited: GfaGraph, source_name: Optional[str] = None) -> Dict[str, Any]:
    steps: List[Dict[str, Any]] = []
    warnings: List[str] = []
    consumed_original_ids: Set[str] = set()

    original_ids = set(original.segments)
    edited_ids = set(edited.segments)
    removed_ids = original_ids - edited_ids
    added_ids = edited_ids - original_ids

    for node_id in sorted(original_ids & edited_ids):
        original_segment = original.segments[node_id]
        edited_segment = edited.segments[node_id]
        rotation_offset = _rotation_offset(original_segment.sequence, edited_segment.sequence)
        if rotation_offset:
            steps.append(_inferred_step("rotate_circular_node", {"node_id": node_id, "offset": rotation_offset}))
        update_params = _infer_node_update_params(node_id, original_segment, edited_segment)
        if len(update_params) > 1:
            steps.append(_inferred_step("update_node", update_params))

    for new_id in sorted(added_ids):
        merge_node_ids = _split_merged_node_id(new_id, original_ids)
        if len(merge_node_ids) >= 2 and all(node_id in removed_ids for node_id in merge_node_ids):
            merge_steps, merge_warnings = _infer_merge_steps(
                original,
                merge_node_ids,
                edited.segments[new_id],
                new_id,
            )
            steps.extend(merge_steps)
            warnings.extend(merge_warnings)
            consumed_original_ids.update(merge_node_ids)
            continue

        rename_source = _find_unique_sequence_match(removed_ids - consumed_original_ids, original, edited.segments[new_id])
        if rename_source:
            params = {"node_id": rename_source, "name": new_id}
            params.update(_infer_node_update_params(rename_source, original.segments[rename_source], edited.segments[new_id], include_name=False))
            steps.append(_inferred_step("update_node", params))
            consumed_original_ids.add(rename_source)
            continue

        duplicate_source = _find_unique_sequence_match(original_ids - consumed_original_ids, original, edited.segments[new_id])
        if duplicate_source:
            steps.append(_inferred_step("duplicate_node", {"node_id": duplicate_source, "new_id": new_id}))
            continue

        warnings.append(f"Could not infer how new contig {new_id} was created")

    for node_id in sorted(removed_ids - consumed_original_ids):
        steps.append(_inferred_step("delete_node", {"node_id": node_id}))

    warnings.extend(_infer_link_warnings(original, edited))
    return build_history_document(steps, source_name=source_name, warnings=warnings)


def _inferred_step(action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    return {"action": action, "params": copy.deepcopy(params), "inferred": True}


def _infer_node_update_params(
    node_id: str,
    original_segment,
    edited_segment,
    include_name: bool = True,
) -> Dict[str, Any]:
    params: Dict[str, Any] = {"node_id": node_id}
    if include_name and original_segment.id != edited_segment.id:
        params["name"] = edited_segment.id
    if original_segment.depth != edited_segment.depth:
        params["depth"] = edited_segment.depth
    original_label = _string_tag(original_segment.tags, "LB")
    edited_label = _string_tag(edited_segment.tags, "LB")
    if original_label != edited_label:
        params["label"] = edited_label or ""
    original_color = _string_tag(original_segment.tags, "CL")
    edited_color = _string_tag(edited_segment.tags, "CL")
    if original_color != edited_color:
        params["color"] = edited_color or ""
    return params


def _split_merged_node_id(node_id: str, original_ids: Set[str]) -> List[str]:
    parts: List[str] = []
    remaining = node_id
    sorted_ids = sorted(original_ids, key=len, reverse=True)
    while remaining:
        match = next((candidate for candidate in sorted_ids if remaining == candidate or remaining.startswith(f"{candidate}_")), None)
        if not match:
            return []
        parts.append(match)
        remaining = remaining[len(match) :]
        if remaining.startswith("_"):
            remaining = remaining[1:]
        elif remaining:
            return []
    return parts


def _find_unique_sequence_match(candidate_ids: Iterable[str], original: GfaGraph, edited_segment) -> Optional[str]:
    matches = [
        node_id
        for node_id in candidate_ids
        if _segment_sequence_key(original.segments[node_id]) == _segment_sequence_key(edited_segment)
    ]
    return matches[0] if len(matches) == 1 else None


def _infer_merge_steps(
    original: GfaGraph,
    merge_node_ids: List[str],
    edited_segment,
    edited_id: str,
) -> tuple:
    steps: List[Dict[str, Any]] = [
        _inferred_step("merge_selection", {"node_ids": merge_node_ids, "edge_ids": []})
    ]
    warnings: List[str] = []

    try:
        simulated = original.clone()
        result = merge_selection(simulated, merge_node_ids, [])
    except (KeyError, ValueError) as exc:
        warnings.append(f"Could not validate inferred merge for {edited_id}: {exc}")
        return steps, warnings

    current_id = str(result["new_node_id"])
    simulated_segment = simulated.segments.get(current_id)
    if simulated_segment is None:
        warnings.append(f"Could not inspect inferred merged contig {current_id}")
        return steps, warnings

    if current_id != edited_id:
        steps.append(_inferred_step("update_node", {"node_id": current_id, "name": edited_id}))
        current_id = edited_id

    rotation_offset = _rotation_offset(simulated_segment.sequence, edited_segment.sequence)
    if rotation_offset:
        has_self_link = any(
            link.source == result["new_node_id"] and link.target == result["new_node_id"]
            for link in simulated.links
        )
        if has_self_link:
            steps.append(_inferred_step("rotate_circular_node", {"node_id": current_id, "offset": rotation_offset}))
        else:
            warnings.append(f"Could not infer sequence rotation for non-circular merged contig {edited_id}")
    elif (
        simulated_segment.sequence is not None
        and edited_segment.sequence is not None
        and simulated_segment.sequence != edited_segment.sequence
    ):
        warnings.append(f"Inferred merge for {edited_id} does not reproduce the edited sequence")

    update_params = _infer_node_update_params(
        current_id,
        simulated_segment,
        edited_segment,
        include_name=False,
    )
    if len(update_params) > 1:
        steps.append(_inferred_step("update_node", update_params))

    return steps, warnings


def _segment_sequence_key(segment) -> tuple:
    return (segment.sequence, segment.length)


def _rotation_offset(original_sequence: Optional[str], edited_sequence: Optional[str]) -> Optional[int]:
    if not original_sequence or not edited_sequence or len(original_sequence) != len(edited_sequence):
        return None
    if original_sequence == edited_sequence:
        return None
    offset = (original_sequence + original_sequence).find(edited_sequence)
    if offset <= 0 or offset >= len(original_sequence):
        return None
    return offset


def _string_tag(tags: Dict[str, Dict[str, Any]], tag: str) -> Optional[str]:
    payload = tags.get(tag)
    if payload is None:
        return None
    value = payload.get("value", payload.get("raw"))
    return None if value is None else str(value)


def _infer_link_warnings(original: GfaGraph, edited: GfaGraph) -> List[str]:
    original_signatures = {_link_signature(link) for link in original.links}
    edited_signatures = {_link_signature(link) for link in edited.links}
    warnings = []
    added = len(edited_signatures - original_signatures)
    removed = len(original_signatures - edited_signatures)
    if added or removed:
        warnings.append(
            "Link-level edits were not fully inferred "
            f"(added signatures: {added}, removed signatures: {removed})"
        )
    return warnings


def _link_signature(link) -> tuple:
    return (
        link.source,
        link.source_orient,
        link.target,
        link.target_orient,
        link.cigar,
        link.support,
    )
