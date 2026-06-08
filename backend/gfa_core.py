# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

from __future__ import annotations

import copy
import hashlib
import math
import re
import time
from dataclasses import dataclass, field
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple


DEPTH_TAGS = ("dp", "DP", "rd", "RD", "cov", "COV", "KC", "RC")
LINK_SUPPORT_TAGS = ("RC", "ec", "EC", "FC", "KC")
CUSTOM_COLOR_TAG = "CL"
CUSTOM_LABEL_TAG = "LB"
_COMPLEMENT = str.maketrans("ACGTRYKMSWBDHVNacgtrykmswbdhvn", "TGCAYRMKSWVHDBNtgcayrmkswvhdbn")
_BLANK_BYTE_LINES = (b"\n", b"\r\n")
_BLANK_TEXT_LINES = ("\n", "\r\n")
_CORE_RECORD_BYTES = (b"H", b"S", b"L")


def _coerce_number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_tag_value(tag_type: str, raw_value: str) -> Any:
    if tag_type in {"i", "I"}:
        try:
            return int(raw_value)
        except ValueError:
            return raw_value
    if tag_type == "f":
        try:
            return float(raw_value)
        except ValueError:
            return raw_value
    return raw_value


def parse_tags(fields: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    tags: Dict[str, Dict[str, Any]] = {}
    for field in fields:
        parts = field.split(":", 2)
        if len(parts) != 3:
            continue
        tag, tag_type, raw_value = parts
        tags[tag] = {
            "type": tag_type,
            "raw": raw_value,
            "value": _parse_tag_value(tag_type, raw_value),
        }
    return tags


def format_tags(tags: Dict[str, Dict[str, Any]]) -> List[str]:
    rendered = []
    for tag, payload in tags.items():
        tag_type = str(payload.get("type", "Z"))
        raw_value = payload.get("raw")
        if raw_value is None:
            raw_value = payload.get("value", "")
        rendered.append(f"{tag}:{tag_type}:{raw_value}")
    return rendered


def _first_numeric_tag(tags: Dict[str, Dict[str, Any]], names: Iterable[str]) -> Optional[float]:
    for name in names:
        payload = tags.get(name)
        if payload is None:
            continue
        number = _coerce_number(payload.get("value", payload.get("raw")))
        if number is not None:
            return number
    return None


def _length_from_tags(tags: Dict[str, Dict[str, Any]]) -> Optional[int]:
    payload = tags.get("LN")
    if payload is None:
        return None
    try:
        return int(payload.get("value", payload.get("raw")))
    except (TypeError, ValueError):
        return None


def _string_tag(tags: Dict[str, Dict[str, Any]], tag: str) -> Optional[str]:
    payload = tags.get(tag)
    if payload is None:
        return None
    value = payload.get("value", payload.get("raw"))
    if value is None:
        return None
    return str(value)


def _set_tag(tags: Dict[str, Dict[str, Any]], tag: str, tag_type: str, value: Any) -> None:
    raw = str(value)
    tags[tag] = {"type": tag_type, "raw": raw, "value": _parse_tag_value(tag_type, raw)}


def _set_or_delete_string_tag(tags: Dict[str, Dict[str, Any]], tag: str, value: Optional[str]) -> None:
    if value is None:
        return
    cleaned = value.strip()
    if cleaned:
        _set_tag(tags, tag, "Z", cleaned)
    else:
        tags.pop(tag, None)


def _validate_color(color: Optional[str]) -> Optional[str]:
    if color is None:
        return None
    cleaned = color.strip()
    if not cleaned:
        return ""
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", cleaned):
        raise ValueError("Color must be a hex value like #2f7d76")
    return cleaned.lower()


def _make_edge_id(index: int, source: str, source_orient: str, target: str, target_orient: str) -> str:
    key = f"{index}:{source}:{source_orient}:{target}:{target_orient}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
    return f"link_{index}_{digest}"


def _canonical_link_key(source: str, source_orient: str, target: str, target_orient: str) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    source_endpoint = (source, _gfa_endpoint_side(source_orient, "source"))
    target_endpoint = (target, _gfa_endpoint_side(target_orient, "target"))
    return tuple(sorted((source_endpoint, target_endpoint)))


def renumber_links(graph: "GfaGraph") -> None:
    for index, link in enumerate(graph.links):
        link.id = _make_edge_id(index, link.source, link.source_orient, link.target, link.target_orient)


@dataclass
class Segment:
    id: str
    sequence: Optional[str]
    length: int
    depth: Optional[float] = None
    tags: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blast_hits: List[Dict[str, Any]] = field(default_factory=list)

    def clone(self, new_id: str) -> "Segment":
        duplicate = copy.deepcopy(self)
        duplicate.id = new_id
        return duplicate


@dataclass
class Link:
    id: str
    source: str
    source_orient: str
    target: str
    target_orient: str
    cigar: str = "0M"
    support: Optional[float] = None
    tags: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blast_hits: List[Dict[str, Any]] = field(default_factory=list)

    def clone_with_endpoint(self, original_id: str, duplicate_id: str, edge_index: int) -> "Link":
        duplicate = copy.deepcopy(self)
        duplicate.source = duplicate_id if self.source == original_id else self.source
        duplicate.target = duplicate_id if self.target == original_id else self.target
        duplicate.id = _make_edge_id(
            edge_index,
            duplicate.source,
            duplicate.source_orient,
            duplicate.target,
            duplicate.target_orient,
        )
        return duplicate


def unique_links(links: Iterable[Link]) -> List[Link]:
    seen_link_keys: set[Tuple[Tuple[str, str], Tuple[str, str]]] = set()
    unique: List[Link] = []
    for link in links:
        link_key = _canonical_link_key(link.source, link.source_orient, link.target, link.target_orient)
        if link_key in seen_link_keys:
            continue
        seen_link_keys.add(link_key)
        unique.append(link)
    return unique


def deduplicate_links(graph: "GfaGraph") -> int:
    unique = unique_links(graph.links)
    removed = len(graph.links) - len(unique)
    if removed:
        graph.links = unique
    return removed


@dataclass
class GfaGraph:
    headers: List[List[str]] = field(default_factory=list)
    segments: Dict[str, Segment] = field(default_factory=dict)
    links: List[Link] = field(default_factory=list)
    other_records: List[List[str]] = field(default_factory=list)
    dropped_sequences: bool = False

    def clone(self) -> "GfaGraph":
        return copy.deepcopy(self)

    def stats(self) -> Dict[str, Any]:
        links = unique_links(self.links)
        lengths = [segment.length for segment in self.segments.values()]
        depths = [
            segment.depth
            for segment in self.segments.values()
            if segment.depth is not None and math.isfinite(segment.depth)
        ]
        supports = [
            link.support
            for link in links
            if link.support is not None and math.isfinite(link.support)
        ]
        return {
            "node_count": len(self.segments),
            "edge_count": len(links),
            "total_bp": sum(lengths),
            "min_depth": min(depths) if depths else None,
            "max_depth": max(depths) if depths else None,
            "median_depth": median(depths) if depths else None,
            "max_support": max(supports) if supports else None,
            "sequence_count": sum(1 for segment in self.segments.values() if segment.sequence is not None),
            "has_sequences": any(segment.sequence is not None for segment in self.segments.values()),
            "dropped_sequences": self.dropped_sequences,
        }

    def to_client(self, include_sequences: bool = False) -> Dict[str, Any]:
        stats = self.stats()
        max_depth = stats["max_depth"] or 1
        max_length = max((segment.length for segment in self.segments.values()), default=1)
        max_support = stats["max_support"] or 1
        links = unique_links(self.links)

        nodes = []
        for segment in self.segments.values():
            normalized_depth = (segment.depth or 0) / max_depth if max_depth else 0
            normalized_length = math.log10(max(segment.length, 1)) / math.log10(max(max_length, 10))
            custom_label = _string_tag(segment.tags, CUSTOM_LABEL_TAG)
            custom_color = _string_tag(segment.tags, CUSTOM_COLOR_TAG)
            data: Dict[str, Any] = {
                "id": segment.id,
                "label": custom_label or segment.id,
                "customLabel": custom_label,
                "customColor": custom_color,
                "length": segment.length,
                "depth": segment.depth,
                "degree": 0,
                "color": depth_color(normalized_depth),
                "size": 24 + round(normalized_length * 34, 2),
                "bandageWidth": 56 + round(normalized_length * 130, 2),
                "bandageHeight": 18,
                "tags": compact_tags(segment.tags),
                "blastBest": best_blast_hit(segment.blast_hits),
                "blastHitCount": len(segment.blast_hits),
                "alignmentSpans": alignment_spans(segment.id, segment.length, segment.blast_hits),
            }
            if include_sequences and segment.sequence is not None:
                data["sequence"] = segment.sequence
            nodes.append({"data": data})

        degree_by_id = {segment_id: 0 for segment_id in self.segments}
        edges = []
        for link in links:
            if link.source not in self.segments or link.target not in self.segments:
                continue
            degree_by_id[link.source] = degree_by_id.get(link.source, 0) + 1
            degree_by_id[link.target] = degree_by_id.get(link.target, 0) + 1
            normalized_support = (link.support or 0) / max_support if max_support else 0
            custom_label = _string_tag(link.tags, CUSTOM_LABEL_TAG)
            custom_color = _string_tag(link.tags, CUSTOM_COLOR_TAG)
            edges.append(
                {
                    "data": {
                        "id": link.id,
                        "source": link.source,
                        "target": link.target,
                        "label": custom_label or format_edge_label(link),
                        "customLabel": custom_label,
                        "customColor": custom_color,
                        "sourceOrient": link.source_orient,
                        "targetOrient": link.target_orient,
                        "cigar": link.cigar,
                        "support": link.support,
                        "width": 1.5 + round(normalized_support * 5, 2),
                        "tags": compact_tags(link.tags),
                        "blastBest": best_blast_hit(link.blast_hits),
                        "blastHitCount": len(link.blast_hits),
                    }
                }
            )

        for node in nodes:
            node["data"]["degree"] = degree_by_id.get(node["data"]["id"], 0)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": stats,
            "histogram": histogram_values([node["data"].get("depth") for node in nodes]),
        }


def depth_color(value: float) -> str:
    clamped = max(0.0, min(value, 1.0))
    low = (228, 235, 225)
    mid = (89, 146, 137)
    high = (184, 86, 61)
    if clamped < 0.55:
        t = clamped / 0.55
        rgb = tuple(round(low[i] + (mid[i] - low[i]) * t) for i in range(3))
    else:
        t = (clamped - 0.55) / 0.45
        rgb = tuple(round(mid[i] + (high[i] - mid[i]) * t) for i in range(3))
    return f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"


def compact_tags(tags: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    return {tag: payload.get("value", payload.get("raw")) for tag, payload in tags.items()}


def histogram_values(values: Iterable[Optional[float]], bins: int = 18) -> List[Dict[str, float]]:
    clean = [value for value in values if value is not None and math.isfinite(value)]
    if not clean:
        return []
    low = min(clean)
    high = max(clean)
    if low == high:
        return [{"x0": low, "x1": high, "count": len(clean)}]
    step = (high - low) / bins
    counts = [0] * bins
    for value in clean:
        index = min(int((value - low) / step), bins - 1)
        counts[index] += 1
    return [
        {"x0": low + index * step, "x1": low + (index + 1) * step, "count": count}
        for index, count in enumerate(counts)
    ]


def best_blast_hit(hits: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not hits:
        return None
    return max(
        hits,
        key=lambda hit: (
            hit.get("bitscore") or 0,
            hit.get("pident") or 0,
            hit.get("length") or hit.get("alnlen") or 0,
            hit.get("mapq") or 0,
        ),
    )


def alignment_spans(segment_id: str, segment_length: int, hits: List[Dict[str, Any]], limit: int = 120) -> List[Dict[str, Any]]:
    spans: List[Dict[str, Any]] = []
    for hit in hits[:limit]:
        start, end = alignment_target_span(segment_id, hit)
        if start is None or end is None:
            continue
        if start > end:
            start, end = end, start
        start = max(1, min(int(start), max(segment_length, 1)))
        end = max(1, min(int(end), max(segment_length, 1)))
        if end < start:
            continue
        spans.append(
            {
                "start": start,
                "end": end,
                "qseqid": hit.get("qseqid"),
                "pident": hit.get("pident"),
                "mapq": hit.get("mapq"),
                "length": hit.get("length") or hit.get("alnlen"),
                "strand": hit.get("strand"),
            }
        )
    return spans


def alignment_target_span(segment_id: str, hit: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    if str(hit.get("sseqid") or "") == segment_id:
        return _optional_int(hit.get("sstart")), _optional_int(hit.get("send"))
    if str(hit.get("qseqid") or "") == segment_id:
        return _optional_int(hit.get("qstart")), _optional_int(hit.get("qend"))
    return None, None


def _optional_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def format_edge_label(link: Link) -> str:
    if link.support is None:
        return f"{link.source_orient}/{link.target_orient}"
    support = int(link.support) if float(link.support).is_integer() else round(link.support, 2)
    return f"RC {support}"


def parse_gfa_lines(
    lines: Iterable[Any],
    keep_sequences: bool = False,
    sequence_time_limit_seconds: Optional[float] = None,
    keep_other_records: bool = True,
) -> GfaGraph:
    graph = GfaGraph(dropped_sequences=not keep_sequences)
    edge_index = 0
    seen_link_keys: set[Tuple[Tuple[str, str], Tuple[str, str]]] = set()
    keep_segment_sequences = keep_sequences
    sequence_deadline = (
        time.monotonic() + sequence_time_limit_seconds
        if keep_sequences and sequence_time_limit_seconds is not None
        else None
    )
    for line_number, raw_line in enumerate(lines, start=1):
        if isinstance(raw_line, bytes):
            if not raw_line or raw_line in _BLANK_BYTE_LINES:
                continue
            if not keep_other_records and raw_line[:1] not in _CORE_RECORD_BYTES:
                continue
            raw_line = raw_line.decode("utf-8", errors="replace")
        elif not isinstance(raw_line, str):
            raw_line = str(raw_line)
        if not raw_line or raw_line in _BLANK_TEXT_LINES:
            continue
        fields = raw_line.rstrip("\r\n").split("\t")
        record_type = fields[0]
        if record_type == "H":
            graph.headers.append(fields)
            continue
        if record_type == "S":
            if len(fields) < 3:
                raise ValueError(f"Invalid S record on line {line_number}: expected at least 3 fields")
            name = fields[1]
            raw_sequence = fields[2]
            tags = parse_tags(fields[3:])
            tagged_length = _length_from_tags(tags)
            sequence_length = 0 if raw_sequence == "*" else len(raw_sequence)
            length = tagged_length if tagged_length is not None else sequence_length
            if (
                keep_segment_sequences
                and sequence_deadline is not None
                and time.monotonic() > sequence_deadline
            ):
                keep_segment_sequences = False
                graph.dropped_sequences = True
                for segment in graph.segments.values():
                    segment.sequence = None
            graph.segments[name] = Segment(
                id=name,
                sequence=raw_sequence if keep_segment_sequences and raw_sequence != "*" else None,
                length=length,
                depth=_first_numeric_tag(tags, DEPTH_TAGS),
                tags=tags,
            )
            continue
        if record_type == "L":
            if len(fields) < 6:
                raise ValueError(f"Invalid L record on line {line_number}: expected at least 6 fields")
            tags = parse_tags(fields[6:])
            link = Link(
                id=_make_edge_id(edge_index, fields[1], fields[2], fields[3], fields[4]),
                source=fields[1],
                source_orient=fields[2],
                target=fields[3],
                target_orient=fields[4],
                cigar=fields[5],
                support=_first_numeric_tag(tags, LINK_SUPPORT_TAGS),
                tags=tags,
            )
            link_key = _canonical_link_key(
                link.source,
                link.source_orient,
                link.target,
                link.target_orient,
            )
            if link_key in seen_link_keys:
                continue
            seen_link_keys.add(link_key)
            graph.links.append(link)
            edge_index += 1
            continue
        if keep_other_records:
            graph.other_records.append(fields)
    return graph


def parse_gfa_text(
    text: str,
    keep_sequences: bool = False,
    sequence_time_limit_seconds: Optional[float] = None,
    keep_other_records: bool = True,
) -> GfaGraph:
    return parse_gfa_lines(
        text.splitlines(),
        keep_sequences=keep_sequences,
        sequence_time_limit_seconds=sequence_time_limit_seconds,
        keep_other_records=keep_other_records,
    )


def delete_node(graph: GfaGraph, node_id: str) -> Dict[str, Any]:
    if node_id not in graph.segments:
        raise KeyError(f"Node not found: {node_id}")
    del graph.segments[node_id]
    before = len(graph.links)
    graph.links = [link for link in graph.links if link.source != node_id and link.target != node_id]
    return {"node_id": node_id, "removed_edges": before - len(graph.links)}


def delete_edge(graph: GfaGraph, edge_id: str) -> Dict[str, Any]:
    before = len(graph.links)
    graph.links = [link for link in graph.links if link.id != edge_id]
    if len(graph.links) == before:
        raise KeyError(f"Edge not found: {edge_id}")
    return {"edge_id": edge_id}


def delete_selection(
    graph: GfaGraph,
    node_ids: Iterable[str],
    edge_ids: Iterable[str],
) -> Dict[str, Any]:
    selected_node_ids = _unique_nonempty_ids(node_ids)
    selected_edge_ids = _unique_nonempty_ids(edge_ids)
    if not selected_node_ids and not selected_edge_ids:
        raise ValueError("Select one or more contigs or links to delete")

    missing_node_ids = [node_id for node_id in selected_node_ids if node_id not in graph.segments]
    if missing_node_ids:
        raise KeyError(f"Node not found: {missing_node_ids[0]}")

    link_by_id = {link.id: link for link in graph.links}
    missing_edge_ids = [edge_id for edge_id in selected_edge_ids if edge_id not in link_by_id]
    if missing_edge_ids:
        raise KeyError(f"Link not found: {missing_edge_ids[0]}")

    selected_nodes = set(selected_node_ids)
    selected_edges = set(selected_edge_ids)
    before_edges = len(graph.links)
    for node_id in selected_node_ids:
        del graph.segments[node_id]
    graph.links = [
        link
        for link in graph.links
        if link.id not in selected_edges
        and link.source not in selected_nodes
        and link.target not in selected_nodes
    ]
    return {
        "node_ids": selected_node_ids,
        "edge_ids": selected_edge_ids,
        "removed_nodes": len(selected_node_ids),
        "removed_edges": before_edges - len(graph.links),
    }


def update_node(
    graph: GfaGraph,
    node_id: str,
    name: Optional[str] = None,
    label: Optional[str] = None,
    color: Optional[str] = None,
    depth: Optional[float] = None,
) -> Dict[str, Any]:
    if node_id not in graph.segments:
        raise KeyError(f"Node not found: {node_id}")
    segment = graph.segments[node_id]
    old_id = node_id
    new_id = name.strip() if name is not None else node_id
    if not new_id:
        raise ValueError("Node name cannot be empty")
    if new_id != old_id:
        if new_id in graph.segments:
            raise ValueError(f"Node id already exists: {new_id}")
        renamed_segments: Dict[str, Segment] = {}
        for current_id, current_segment in graph.segments.items():
            if current_id == old_id:
                current_segment.id = new_id
                renamed_segments[new_id] = current_segment
            else:
                renamed_segments[current_id] = current_segment
        graph.segments = renamed_segments
        for link in graph.links:
            if link.source == old_id:
                link.source = new_id
            if link.target == old_id:
                link.target = new_id
        renumber_links(graph)
        segment = graph.segments[new_id]

    cleaned_color = _validate_color(color)
    _set_or_delete_string_tag(segment.tags, CUSTOM_LABEL_TAG, label)
    _set_or_delete_string_tag(segment.tags, CUSTOM_COLOR_TAG, cleaned_color)
    if depth is not None:
        segment.depth = float(depth)
        tag_type = "i" if float(depth).is_integer() else "f"
        _set_tag(segment.tags, "dp", tag_type, int(depth) if tag_type == "i" else float(depth))
    return {"old_node_id": old_id, "new_node_id": new_id}


def update_edge(
    graph: GfaGraph,
    edge_id: str,
    label: Optional[str] = None,
    color: Optional[str] = None,
    support: Optional[float] = None,
    cigar: Optional[str] = None,
) -> Dict[str, Any]:
    link = next((candidate for candidate in graph.links if candidate.id == edge_id), None)
    if link is None:
        raise KeyError(f"Edge not found: {edge_id}")
    cleaned_color = _validate_color(color)
    _set_or_delete_string_tag(link.tags, CUSTOM_LABEL_TAG, label)
    _set_or_delete_string_tag(link.tags, CUSTOM_COLOR_TAG, cleaned_color)
    if support is not None:
        link.support = float(support)
        tag_type = "i" if float(support).is_integer() else "f"
        _set_tag(link.tags, "RC", tag_type, int(support) if tag_type == "i" else float(support))
    if cigar is not None:
        cleaned_cigar = cigar.strip()
        if not cleaned_cigar:
            raise ValueError("CIGAR cannot be empty")
        link.cigar = cleaned_cigar
    return {"edge_id": edge_id}


def rotate_circular_node(graph: GfaGraph, node_id: str, offset: int) -> Dict[str, Any]:
    if node_id not in graph.segments:
        raise KeyError(f"Node not found: {node_id}")
    segment = graph.segments[node_id]
    if segment.sequence is None:
        raise ValueError("Rotate circular start requires loading the GFA with sequences preserved")
    length = len(segment.sequence)
    if length <= 0:
        raise ValueError("Cannot rotate an empty sequence")
    normalized_offset = int(offset) % length
    if normalized_offset == 0:
        return {"node_id": node_id, "offset": 0, "length": length}
    incident_links = [
        link
        for link in graph.links
        if link.source == node_id or link.target == node_id
    ]
    self_links = [
        link.id
        for link in incident_links
        if link.source == node_id and link.target == node_id
    ]
    if len(incident_links) != 1 or len(self_links) != 1:
        raise ValueError("Rotate circular start requires the selected contig to have exactly one self-loop")
    segment.sequence = segment.sequence[normalized_offset:] + segment.sequence[:normalized_offset]
    segment.length = len(segment.sequence)
    _set_tag(segment.tags, "LN", "i", segment.length)
    return {
        "node_id": node_id,
        "offset": normalized_offset,
        "length": segment.length,
        "self_links": self_links,
    }


def duplicate_node(graph: GfaGraph, node_id: str, requested_id: Optional[str] = None) -> Dict[str, Any]:
    if node_id not in graph.segments:
        raise KeyError(f"Node not found: {node_id}")
    new_id = requested_id or next_duplicate_id(graph.segments.keys(), node_id)
    if new_id in graph.segments:
        raise ValueError(f"Duplicate node id already exists: {new_id}")
    graph.segments[new_id] = graph.segments[node_id].clone(new_id)

    incident_links = [
        link for link in graph.links if link.source == node_id or link.target == node_id
    ]
    seen_link_keys = {
        _canonical_link_key(link.source, link.source_orient, link.target, link.target_orient)
        for link in graph.links
    }
    edge_index = len(graph.links)
    copied_links: List[Link] = []
    for link in incident_links:
        copied_link = link.clone_with_endpoint(node_id, new_id, edge_index)
        edge_index += 1
        copied_link_key = _canonical_link_key(
            copied_link.source,
            copied_link.source_orient,
            copied_link.target,
            copied_link.target_orient,
        )
        if copied_link_key in seen_link_keys:
            continue
        seen_link_keys.add(copied_link_key)
        copied_links.append(copied_link)
    graph.links.extend(copied_links)
    return {"source_node_id": node_id, "new_node_id": new_id, "copied_edges": len(copied_links)}


def merge_link(
    graph: GfaGraph,
    edge_id: str,
    allow_source_endpoint_links: bool = False,
    allow_target_endpoint_links: bool = False,
) -> Dict[str, Any]:
    merge_link_record = next((candidate for candidate in graph.links if candidate.id == edge_id), None)
    if merge_link_record is None:
        raise KeyError(f"Link not found: {edge_id}")
    source_id = merge_link_record.source
    target_id = merge_link_record.target
    if source_id == target_id:
        raise ValueError("Cannot merge a self-link")
    if source_id not in graph.segments or target_id not in graph.segments:
        raise KeyError("Cannot merge link with missing endpoint segment")

    source_side = _link_endpoint_side(merge_link_record, source_id)
    target_side = _link_endpoint_side(merge_link_record, target_id)
    if source_side is None or target_side is None:
        raise ValueError("Selected link does not attach to both merge endpoints")
    if not allow_source_endpoint_links:
        _validate_merge_endpoint(graph, source_id, source_side, edge_id)
    if not allow_target_endpoint_links:
        _validate_merge_endpoint(graph, target_id, target_side, edge_id)

    if any(
        link.id != edge_id
        and {link.source, link.target} == {source_id, target_id}
        for link in graph.links
    ):
        raise ValueError("Cannot merge nodes with additional links between them")

    source_segment = graph.segments[source_id]
    target_segment = graph.segments[target_id]
    overlap = _overlap_length_from_cigar(merge_link_record.cigar)
    new_id = next_merged_id(graph.segments.keys(), source_id, target_id)
    new_segment = _merged_segment(
        source_segment,
        target_segment,
        new_id,
        merge_link_record.source_orient,
        merge_link_record.target_orient,
        overlap,
    )

    rewired_links: List[Link] = []
    removed_edge_ids = [edge_id]
    for link in unique_links(graph.links):
        if link.id == edge_id:
            continue
        duplicate = copy.deepcopy(link)
        touches_source = duplicate.source == source_id or duplicate.target == source_id
        touches_target = duplicate.source == target_id or duplicate.target == target_id
        if touches_source and touches_target:
            raise ValueError("Cannot merge nodes with links that would become self-links")
        if touches_source:
            _replace_link_endpoint(duplicate, source_id, new_id, "-")
        if touches_target:
            _replace_link_endpoint(duplicate, target_id, new_id, "+")
        rewired_links.append(duplicate)

    merged_segments: Dict[str, Segment] = {}
    inserted = False
    for segment_id, segment in graph.segments.items():
        if segment_id == source_id:
            merged_segments[new_id] = new_segment
            inserted = True
            continue
        if segment_id == target_id:
            if not inserted:
                merged_segments[new_id] = new_segment
                inserted = True
            continue
        merged_segments[segment_id] = segment
    graph.segments = merged_segments
    graph.links = rewired_links
    return {
        "edge_id": edge_id,
        "source_node_id": source_id,
        "target_node_id": target_id,
        "new_node_id": new_id,
        "removed_edges": removed_edge_ids,
        "overlap": overlap,
    }


def merge_selection(
    graph: GfaGraph,
    node_ids: Iterable[str],
    edge_ids: Iterable[str],
) -> Dict[str, Any]:
    selected_node_ids = _unique_nonempty_ids(node_ids)
    selected_edge_ids = _unique_nonempty_ids(edge_ids)
    if len(selected_node_ids) < 2:
        if len(selected_edge_ids) == 1:
            result = merge_link(graph, selected_edge_ids[0])
            return {
                **result,
                "node_ids": [result["source_node_id"], result["target_node_id"]],
                "path_node_ids": [result["source_node_id"], result["target_node_id"]],
                "path_edge_ids": [selected_edge_ids[0]],
                "merged_steps": [result],
            }
        if len(selected_edge_ids) == 2:
            selected_node_ids = _node_ids_from_two_link_cycle(graph, selected_edge_ids)
        else:
            raise ValueError("Select one link, two cycle links, or at least two contigs to merge")

    missing_node_ids = [node_id for node_id in selected_node_ids if node_id not in graph.segments]
    if missing_node_ids:
        raise KeyError(f"Node not found: {missing_node_ids[0]}")

    link_by_id = {link.id: link for link in graph.links}
    missing_edge_ids = [edge_id for edge_id in selected_edge_ids if edge_id not in link_by_id]
    if missing_edge_ids:
        raise KeyError(f"Link not found: {missing_edge_ids[0]}")

    path_node_ids, path_links, retained_cycle_link = _selected_merge_path(
        graph,
        selected_node_ids,
        selected_edge_ids,
    )
    path_edge_ids = [link.id for link in path_links]
    allowed_selected_edge_ids = set(path_edge_ids)
    if retained_cycle_link is not None:
        allowed_selected_edge_ids.add(retained_cycle_link.id)
    extra_selected_edge_ids = [edge_id for edge_id in selected_edge_ids if edge_id not in allowed_selected_edge_ids]
    if extra_selected_edge_ids:
        raise ValueError("Selected links must be the unique links between selected contigs")

    _validate_selected_path_external_links(
        graph,
        path_node_ids,
        path_edge_ids,
        retained_cycle_link.id if retained_cycle_link else None,
    )
    _validate_selected_path_sides(
        graph,
        path_node_ids,
        path_edge_ids,
        retained_cycle_link.id if retained_cycle_link else None,
    )

    retained_cycle_link_copy = copy.deepcopy(retained_cycle_link) if retained_cycle_link else None
    if retained_cycle_link is not None:
        graph.links = [link for link in graph.links if link.id != retained_cycle_link.id]

    current_node_id = path_node_ids[0]
    merged_steps: List[Dict[str, Any]] = []
    removed_edge_ids: List[str] = []
    total_overlap = 0
    for index, next_node_id in enumerate(path_node_ids[1:]):
        link = _unique_link_between_nodes(graph, current_node_id, next_node_id)
        allow_source_endpoint_links = False
        allow_target_endpoint_links = False
        if index == 0:
            if link.source == path_node_ids[0]:
                allow_source_endpoint_links = True
            if link.target == path_node_ids[0]:
                allow_target_endpoint_links = True
        if index == len(path_node_ids) - 2:
            if link.source == next_node_id:
                allow_source_endpoint_links = True
            if link.target == next_node_id:
                allow_target_endpoint_links = True
        result = merge_link(
            graph,
            link.id,
            allow_source_endpoint_links=allow_source_endpoint_links,
            allow_target_endpoint_links=allow_target_endpoint_links,
        )
        merged_steps.append(result)
        removed_edge_ids.extend(result.get("removed_edges", [link.id]))
        total_overlap += int(result.get("overlap", 0))
        current_node_id = result["new_node_id"]

    retained_edge_ids: List[str] = []
    if retained_cycle_link_copy is not None:
        _replace_link_endpoint(retained_cycle_link_copy, path_node_ids[0], current_node_id, "-")
        _replace_link_endpoint(retained_cycle_link_copy, path_node_ids[-1], current_node_id, "+")
        graph.links.append(retained_cycle_link_copy)
        retained_edge_ids = [retained_cycle_link_copy.id]

    return {
        "node_ids": selected_node_ids,
        "edge_ids": selected_edge_ids,
        "path_node_ids": path_node_ids,
        "path_edge_ids": path_edge_ids,
        "retained_cycle_edge_ids": retained_edge_ids,
        "new_node_id": current_node_id,
        "removed_edges": removed_edge_ids,
        "merged_steps": merged_steps,
        "overlap": total_overlap,
    }


def _node_ids_from_two_link_cycle(graph: GfaGraph, edge_ids: List[str]) -> List[str]:
    link_by_id = {link.id: link for link in graph.links}
    links = [link_by_id.get(edge_id) for edge_id in edge_ids]
    if any(link is None for link in links):
        missing_edge_id = edge_ids[links.index(None)]
        raise KeyError(f"Link not found: {missing_edge_id}")
    first, second = links
    if first.source == first.target or second.source == second.target:
        raise ValueError("Selected cycle links must connect two different contigs")
    if {first.source, first.target} != {second.source, second.target}:
        raise ValueError("Selected cycle links must connect the same two contigs")
    return [first.source, first.target]


def _unique_nonempty_ids(ids: Iterable[str]) -> List[str]:
    unique_ids: List[str] = []
    seen = set()
    for raw_id in ids or []:
        item_id = str(raw_id).strip()
        if not item_id or item_id in seen:
            continue
        unique_ids.append(item_id)
        seen.add(item_id)
    return unique_ids


def _selected_merge_path(graph: GfaGraph, node_ids: List[str], edge_ids: Optional[List[str]] = None) -> tuple:
    selected = set(node_ids)
    internal_links = [
        link
        for link in graph.links
        if link.source in selected and link.target in selected and link.source != link.target
    ]

    adjacency: Dict[str, List[Link]] = {node_id: [] for node_id in node_ids}
    pair_counts: Dict[frozenset, int] = {}
    for link in internal_links:
        pair_key = frozenset((link.source, link.target))
        pair_counts[pair_key] = pair_counts.get(pair_key, 0) + 1
        adjacency[link.source].append(link)
        adjacency[link.target].append(link)

    if len(selected) == 2 and len(internal_links) == 2:
        return _selected_merge_two_node_cycle_path(node_ids, internal_links, edge_ids or [])

    if any(count != 1 for count in pair_counts.values()):
        raise ValueError("Selected contigs must have exactly one link between each connected pair")

    if len(internal_links) == len(selected):
        return _selected_merge_cycle_path(node_ids, adjacency)

    if len(internal_links) != len(selected) - 1:
        raise ValueError("Selected contigs must form a single path or simple cycle")

    endpoints = [node_id for node_id in node_ids if len(adjacency[node_id]) == 1]
    middle_nodes = [node_id for node_id in node_ids if len(adjacency[node_id]) == 2]
    if len(selected) == 2:
        valid_degrees = len(endpoints) == 2
    else:
        valid_degrees = len(endpoints) == 2 and len(middle_nodes) == len(selected) - 2
    if not valid_degrees:
        raise ValueError("Selected contigs must form one unbranched head-to-tail path")

    start_node_id = min(endpoints, key=node_ids.index)
    path_node_ids = [start_node_id]
    path_links: List[Link] = []
    seen = {start_node_id}
    previous_node_id: Optional[str] = None
    current_node_id = start_node_id
    while len(path_node_ids) < len(selected):
        candidates = [
            link
            for link in adjacency[current_node_id]
            if _other_link_node(link, current_node_id) != previous_node_id
        ]
        if len(candidates) != 1:
            raise ValueError("Selected contigs must form one unbranched head-to-tail path")
        link = candidates[0]
        next_node_id = _other_link_node(link, current_node_id)
        if next_node_id in seen:
            raise ValueError("Selected contigs must form one unbranched head-to-tail path")
        path_links.append(link)
        path_node_ids.append(next_node_id)
        seen.add(next_node_id)
        previous_node_id = current_node_id
        current_node_id = next_node_id

    if seen != selected:
        raise ValueError("Selected contigs must form one connected path")
    return path_node_ids, path_links, None


def _selected_merge_two_node_cycle_path(
    node_ids: List[str],
    internal_links: List[Link],
    selected_edge_ids: List[str],
) -> tuple:
    if len(internal_links) != 2:
        raise ValueError("Selected contigs must form one two-contig cycle")
    selected_edges = set(selected_edge_ids)
    path_link = next((link for link in internal_links if link.id in selected_edges), internal_links[0])
    retained_link = next(link for link in internal_links if link.id != path_link.id)
    return node_ids, [path_link], retained_link


def _selected_merge_cycle_path(
    node_ids: List[str],
    adjacency: Dict[str, List[Link]],
) -> tuple:
    if len(node_ids) < 3 or any(len(adjacency[node_id]) != 2 for node_id in node_ids):
        raise ValueError("Selected contigs must form one simple cycle")

    start_node_id = node_ids[0]
    start_links = adjacency[start_node_id]
    first_link = next(
        (link for link in start_links if len(node_ids) > 1 and _other_link_node(link, start_node_id) == node_ids[1]),
        start_links[0],
    )
    path_node_ids = [start_node_id]
    path_links: List[Link] = []
    seen = {start_node_id}
    previous_link_id: Optional[str] = None
    current_node_id = start_node_id

    while len(path_node_ids) < len(node_ids):
        candidates = [link for link in adjacency[current_node_id] if link.id != previous_link_id]
        if current_node_id == start_node_id:
            candidates = [first_link]
        if len(candidates) != 1:
            raise ValueError("Selected contigs must form one simple cycle")
        link = candidates[0]
        next_node_id = _other_link_node(link, current_node_id)
        if next_node_id in seen:
            raise ValueError("Selected contigs must form one simple cycle")
        path_links.append(link)
        path_node_ids.append(next_node_id)
        seen.add(next_node_id)
        previous_link_id = link.id
        current_node_id = next_node_id

    retained_candidates = [
        link
        for link in adjacency[current_node_id]
        if link.id != previous_link_id and _other_link_node(link, current_node_id) == start_node_id
    ]
    if len(retained_candidates) != 1 or seen != set(node_ids):
        raise ValueError("Selected contigs must form one simple cycle")
    return path_node_ids, path_links, retained_candidates[0]


def _other_link_node(link: Link, node_id: str) -> str:
    if link.source == node_id:
        return link.target
    if link.target == node_id:
        return link.source
    raise ValueError(f"Link {link.id} is not attached to {node_id}")


def _validate_selected_path_external_links(
    graph: GfaGraph,
    path_node_ids: List[str],
    path_edge_ids: List[str],
    retained_edge_id: Optional[str] = None,
) -> None:
    path_nodes = set(path_node_ids)
    path_edges = set(path_edge_ids)
    internal_nodes = set(path_node_ids[1:-1])
    for link in unique_links(graph.links):
        if link.source == link.target and link.source in path_nodes:
            raise ValueError("Cannot merge a path with self-loop links on selected contigs")
        if link.id in path_edges or link.id == retained_edge_id:
            continue
        if link.source in internal_nodes or link.target in internal_nodes:
            raise ValueError("Selected path has internal contigs with extra links")


def _validate_selected_path_sides(
    graph: GfaGraph,
    path_node_ids: List[str],
    path_edge_ids: List[str],
    retained_edge_id: Optional[str] = None,
) -> None:
    selected_edge_ids = set(path_edge_ids)
    if retained_edge_id is not None:
        selected_edge_ids.add(retained_edge_id)
    selected_links = [link for link in graph.links if link.id in selected_edge_ids]
    checked_node_ids = path_node_ids if retained_edge_id is not None else path_node_ids[1:-1]
    for node_id in checked_node_ids:
        sides = [
            side
            for link in selected_links
            for side in [_link_endpoint_side(link, node_id)]
            if side is not None
        ]
        if len(sides) != 2 or set(sides) != {"-", "+"}:
            raise ValueError(f"Selected contig {node_id} must be connected through opposite ends")


def _unique_link_between_nodes(graph: GfaGraph, first_node_id: str, second_node_id: str) -> Link:
    matches = [
        link
        for link in graph.links
        if link.source != link.target and {link.source, link.target} == {first_node_id, second_node_id}
    ]
    if len(matches) != 1:
        raise ValueError("Merge path no longer has exactly one link between adjacent contigs")
    return matches[0]


def _validate_merge_endpoint(graph: GfaGraph, node_id: str, side: str, selected_edge_id: str) -> None:
    attached = [
        link.id
        for link in graph.links
        if link.id == selected_edge_id or link.source == node_id or link.target == node_id
        if _link_endpoint_side(link, node_id) == side
    ]
    if attached != [selected_edge_id]:
        raise ValueError(
            f"Cannot merge: endpoint {node_id}{side} must have only the selected link"
        )


def _merged_segment(
    source: Segment,
    target: Segment,
    new_id: str,
    source_orient: str,
    target_orient: str,
    overlap: int,
) -> Segment:
    effective_overlap = max(0, min(overlap, source.length, target.length))
    new_length = source.length + target.length - effective_overlap
    sequence = _merge_segment_sequences(source, target, source_orient, target_orient, effective_overlap)
    depth = _weighted_depth(source, target)
    tags = _merge_segment_tags(source, target, new_length, depth)
    return Segment(
        id=new_id,
        sequence=sequence,
        length=len(sequence) if sequence is not None else new_length,
        depth=depth,
        tags=tags,
        blast_hits=[*copy.deepcopy(source.blast_hits), *copy.deepcopy(target.blast_hits)],
    )


def _merge_segment_sequences(
    source: Segment,
    target: Segment,
    source_orient: str,
    target_orient: str,
    overlap: int,
) -> Optional[str]:
    if source.sequence is None or target.sequence is None:
        return None
    source_sequence = _oriented_sequence(source.sequence, source_orient)
    target_sequence = _oriented_sequence(target.sequence, target_orient)
    trimmed_overlap = max(0, min(overlap, len(target_sequence)))
    return source_sequence + target_sequence[trimmed_overlap:]


def _oriented_sequence(sequence: str, orient: str) -> str:
    if orient == "-":
        return sequence.translate(_COMPLEMENT)[::-1]
    return sequence


def _weighted_depth(source: Segment, target: Segment) -> Optional[float]:
    if source.depth is None:
        return target.depth
    if target.depth is None:
        return source.depth
    total_length = max(source.length + target.length, 1)
    return (source.depth * source.length + target.depth * target.length) / total_length


def _merge_segment_tags(source: Segment, target: Segment, length: int, depth: Optional[float]) -> Dict[str, Dict[str, Any]]:
    tags = copy.deepcopy(source.tags)
    for tag, payload in target.tags.items():
        if tag not in tags:
            tags[tag] = copy.deepcopy(payload)
    for tag in ("LN", *DEPTH_TAGS, CUSTOM_LABEL_TAG):
        tags.pop(tag, None)
    if _string_tag(source.tags, CUSTOM_COLOR_TAG) != _string_tag(target.tags, CUSTOM_COLOR_TAG):
        tags.pop(CUSTOM_COLOR_TAG, None)
    _set_tag(tags, "LN", "i", length)
    if depth is not None:
        tag_type = "i" if float(depth).is_integer() else "f"
        _set_tag(tags, "dp", tag_type, int(depth) if tag_type == "i" else round(float(depth), 6))
    return tags


def _replace_link_endpoint(link: Link, old_id: str, new_id: str, new_side: str) -> None:
    if link.source == old_id:
        link.source = new_id
        link.source_orient = _orient_for_endpoint_side(new_side, "source")
    if link.target == old_id:
        link.target = new_id
        link.target_orient = _orient_for_endpoint_side(new_side, "target")


def _orient_for_endpoint_side(side: str, role: str) -> str:
    if role == "target":
        return "-" if side == "+" else "+"
    return "+" if side == "+" else "-"


def _overlap_length_from_cigar(cigar: str) -> int:
    if not cigar or cigar == "*":
        return 0
    total = 0
    for length, op in re.findall(r"(\d+)([MIDNSHP=X])", cigar):
        if op in {"M", "=", "X"}:
            total += int(length)
    return total


def repeat_resolve_node(graph: GfaGraph, node_id: str, duplicate_id: str, strategy: str) -> Dict[str, Any]:
    if node_id not in graph.segments:
        raise KeyError(f"Node not found: {node_id}")
    if duplicate_id not in graph.segments:
        raise KeyError(f"Duplicate node not found: {duplicate_id}")
    if node_id == duplicate_id:
        raise ValueError("Repeat resolution requires two different nodes")
    normalized_strategy = strategy.upper()
    if normalized_strategy not in {"A", "B"}:
        raise ValueError("Repeat resolution strategy must be A or B")

    source_groups = _incident_links_by_side(graph, node_id)
    duplicate_groups = _incident_links_by_side(graph, duplicate_id)
    _validate_repeat_resolution_groups(node_id, source_groups)
    _validate_repeat_resolution_groups(duplicate_id, duplicate_groups)
    copied_by_source = _match_duplicate_links(source_groups, duplicate_groups, node_id, duplicate_id)

    minus_links = source_groups["-"]
    plus_links = source_groups["+"]
    if normalized_strategy == "A":
        source_keep = [minus_links[0], plus_links[0]]
        duplicate_keep = [copied_by_source[minus_links[1].id], copied_by_source[plus_links[1].id]]
    else:
        source_keep = [minus_links[0], plus_links[1]]
        duplicate_keep = [copied_by_source[minus_links[1].id], copied_by_source[plus_links[0].id]]

    keep_ids = {link.id for link in [*source_keep, *duplicate_keep]}
    candidate_ids = {
        link.id
        for link in [
            *source_groups["-"],
            *source_groups["+"],
            *duplicate_groups["-"],
            *duplicate_groups["+"],
        ]
    }
    remove_ids = candidate_ids - keep_ids
    graph.links = [link for link in graph.links if link.id not in remove_ids]
    return {
        "source_node_id": node_id,
        "duplicate_node_id": duplicate_id,
        "strategy": normalized_strategy,
        "kept_edges": sorted(keep_ids),
        "removed_edges": sorted(remove_ids),
    }


def _gfa_endpoint_side(orient: str, role: str) -> str:
    if role == "target":
        return "+" if orient == "-" else "-"
    return "-" if orient == "-" else "+"


def _link_endpoint_side(link: Link, node_id: str) -> Optional[str]:
    is_source = link.source == node_id
    is_target = link.target == node_id
    if is_source and is_target:
        raise ValueError("Repeat resolution does not support self-loop links")
    if is_source:
        return _gfa_endpoint_side(link.source_orient, "source")
    if is_target:
        return _gfa_endpoint_side(link.target_orient, "target")
    return None


def _incident_links_by_side(graph: GfaGraph, node_id: str) -> Dict[str, List[Link]]:
    groups: Dict[str, List[Link]] = {"-": [], "+": []}
    for link in graph.links:
        side = _link_endpoint_side(link, node_id)
        if side:
            groups[side].append(link)
    return groups


def _validate_repeat_resolution_groups(node_id: str, groups: Dict[str, List[Link]]) -> None:
    if len(groups["-"]) != 2 or len(groups["+"]) != 2:
        raise ValueError(
            f"Repeat resolution expects {node_id} to have exactly two links on each end; "
            f"found -:{len(groups['-'])}, +:{len(groups['+'])}"
        )


def _repeat_link_signature(link: Link, node_id: str) -> tuple:
    source = "__SELF__" if link.source == node_id else link.source
    target = "__SELF__" if link.target == node_id else link.target
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
        source,
        link.source_orient,
        target,
        link.target_orient,
        link.cigar,
        link.support,
        tags,
    )


def _match_duplicate_links(
    source_groups: Dict[str, List[Link]],
    duplicate_groups: Dict[str, List[Link]],
    node_id: str,
    duplicate_id: str,
) -> Dict[str, Link]:
    duplicate_by_signature: Dict[tuple, List[Link]] = {}
    for link in [*duplicate_groups["-"], *duplicate_groups["+"]]:
        signature = _repeat_link_signature(link, duplicate_id)
        duplicate_by_signature.setdefault(signature, []).append(link)

    copied_by_source: Dict[str, Link] = {}
    for link in [*source_groups["-"], *source_groups["+"]]:
        signature = _repeat_link_signature(link, node_id)
        candidates = duplicate_by_signature.get(signature) or []
        if not candidates:
            raise ValueError(
                "Repeat resolution could not match duplicated links. "
                "Please duplicate the repeat node immediately before resolving it."
            )
        copied_by_source[link.id] = candidates.pop(0)
    return copied_by_source


def next_duplicate_id(existing_ids: Iterable[str], source_id: str) -> str:
    existing = set(existing_ids)
    index = 1
    while True:
        candidate = f"{source_id}_copy{index}"
        if candidate not in existing:
            return candidate
        index += 1


def next_merged_id(existing_ids: Iterable[str], source_id: str, target_id: str) -> str:
    existing = set(existing_ids)
    base = f"{source_id}_{target_id}"
    if base not in existing:
        return base
    index = 1
    while True:
        candidate = f"{base}_merge{index}"
        if candidate not in existing:
            return candidate
        index += 1


def export_gfa(graph: GfaGraph) -> str:
    lines: List[str] = []
    headers = graph.headers or [["H", "VN:Z:1.0"]]
    for header in headers:
        lines.append("\t".join(header))

    for segment in graph.segments.values():
        tags = copy.deepcopy(segment.tags)
        if "LN" not in tags and segment.sequence is None and segment.length:
            tags["LN"] = {"type": "i", "raw": str(segment.length), "value": segment.length}
        sequence = segment.sequence if segment.sequence is not None else "*"
        lines.append("\t".join(["S", segment.id, sequence, *format_tags(tags)]))

    for link in unique_links(graph.links):
        if link.source not in graph.segments or link.target not in graph.segments:
            continue
        lines.append(
            "\t".join(
                [
                    "L",
                    link.source,
                    link.source_orient,
                    link.target,
                    link.target_orient,
                    link.cigar,
                    *format_tags(link.tags),
                ]
            )
        )
    return "\n".join(lines) + "\n"


def export_fasta(graph: GfaGraph) -> str:
    missing_sequences = [segment.id for segment in graph.segments.values() if segment.sequence is None]
    if missing_sequences:
        preview = ", ".join(missing_sequences[:5])
        suffix = "..." if len(missing_sequences) > 5 else ""
        raise ValueError(
            "FASTA export requires sequences. Reload the GFA with '保留序列用于导出' enabled. "
            f"Missing: {preview}{suffix}"
        )
    lines: List[str] = []
    for segment in graph.segments.values():
        header_bits = [segment.id, f"length={segment.length}"]
        if segment.depth is not None:
            header_bits.append(f"depth={segment.depth:g}")
        custom_label = _string_tag(segment.tags, CUSTOM_LABEL_TAG)
        if custom_label:
            header_bits.append(f"label={custom_label}")
        lines.append(">" + " ".join(header_bits))
        sequence = segment.sequence or ""
        lines.extend(sequence[index : index + 80] for index in range(0, len(sequence), 80))
    return "\n".join(lines) + "\n"


def parse_blast_outfmt6(text: str) -> Dict[str, List[Dict[str, Any]]]:
    hits_by_query: Dict[str, List[Dict[str, Any]]] = {}
    columns = [
        "qseqid",
        "sseqid",
        "pident",
        "length",
        "mismatch",
        "gapopen",
        "qstart",
        "qend",
        "sstart",
        "send",
        "evalue",
        "bitscore",
    ]
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split()
        if len(fields) < 12:
            raise ValueError(
                f"Invalid BLAST outfmt 6 row on line {line_number}: expected at least 12 columns"
            )
        hit: Dict[str, Any] = dict(zip(columns, fields[:12]))
        for key in ["pident", "evalue", "bitscore"]:
            hit[key] = _coerce_number(hit[key])
        for key in ["length", "mismatch", "gapopen", "qstart", "qend", "sstart", "send"]:
            try:
                hit[key] = int(hit[key])
            except (TypeError, ValueError):
                pass
        hits_by_query.setdefault(str(hit["qseqid"]), []).append(hit)
    return hits_by_query


def parse_paf(text: str) -> Dict[str, List[Dict[str, Any]]]:
    hits_by_query: Dict[str, List[Dict[str, Any]]] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split("\t")
        if len(fields) < 12:
            raise ValueError(f"Invalid PAF row on line {line_number}: expected at least 12 columns")
        try:
            query_length = int(fields[1])
            query_start = int(fields[2])
            query_end = int(fields[3])
            target_length = int(fields[6])
            target_start = int(fields[7])
            target_end = int(fields[8])
            matches = int(fields[9])
            alignment_length = int(fields[10])
            mapq = int(fields[11])
        except ValueError as exc:
            raise ValueError(f"Invalid numeric field in PAF row on line {line_number}") from exc
        hit: Dict[str, Any] = {
            "format": "paf",
            "qseqid": fields[0],
            "qlen": query_length,
            "qstart": query_start + 1,
            "qend": query_end,
            "strand": fields[4],
            "sseqid": fields[5],
            "slen": target_length,
            "sstart": target_start + 1,
            "send": target_end,
            "matches": matches,
            "length": alignment_length,
            "alnlen": alignment_length,
            "mapq": mapq,
            "pident": (matches / alignment_length * 100) if alignment_length else 0,
        }
        for tag in fields[12:]:
            if tag.startswith("dv:f:"):
                hit["pident"] = max(0, 100 * (1 - _coerce_number(tag[5:])))
            elif tag.startswith("de:f:"):
                hit["gap_compressed_identity"] = max(0, 100 * (1 - _coerce_number(tag[5:])))
            elif tag.startswith("tp:A:"):
                hit["type"] = tag[5:]
        hits_by_query.setdefault(str(hit["qseqid"]), []).append(hit)
    return hits_by_query


def parse_gaf(text: str) -> Dict[str, List[Dict[str, Any]]]:
    hits_by_query: Dict[str, List[Dict[str, Any]]] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        fields = stripped.split("\t")
        if len(fields) < 12:
            raise ValueError(f"Invalid GAF row on line {line_number}: expected at least 12 columns")
        try:
            query_length = int(fields[1])
            query_start = int(fields[2])
            query_end = int(fields[3])
            path_length = int(fields[6])
            path_start = int(fields[7])
            path_end = int(fields[8])
            matches = int(fields[9])
            alignment_length = int(fields[10])
            mapq = int(fields[11])
        except ValueError as exc:
            raise ValueError(f"Invalid numeric field in GAF row on line {line_number}") from exc
        path_segments = parse_gaf_path_segments(fields[5])
        hit: Dict[str, Any] = {
            "format": "gaf",
            "qseqid": fields[0],
            "qlen": query_length,
            "qstart": query_start + 1,
            "qend": query_end,
            "strand": fields[4],
            "path": fields[5],
            "pathSegments": path_segments,
            "sseqid": path_segments[0] if path_segments else fields[5],
            "slen": path_length,
            "sstart": path_start + 1,
            "send": path_end,
            "matches": matches,
            "length": alignment_length,
            "alnlen": alignment_length,
            "mapq": mapq,
            "pident": (matches / alignment_length * 100) if alignment_length else 0,
        }
        for tag in fields[12:]:
            if tag.startswith("dv:f:"):
                hit["pident"] = max(0, 100 * (1 - _coerce_number(tag[5:])))
            elif tag.startswith("tp:A:"):
                hit["type"] = tag[5:]
        hits_by_query.setdefault(str(hit["qseqid"]), []).append(hit)
    return hits_by_query


def parse_gaf_path_segments(path: str) -> List[str]:
    if not path:
        return []
    if path[0] not in "><":
        return [part for part in path.split(",") if part]
    segments: List[str] = []
    current: List[str] = []
    for character in path:
        if character in "><":
            if current:
                segments.append("".join(current))
                current = []
            continue
        current.append(character)
    if current:
        segments.append("".join(current))
    return segments


def parse_alignment_text(text: str, format_value: str) -> Dict[str, List[Dict[str, Any]]]:
    normalized = format_value.lower()
    if normalized in {"blast6", "blast", "outfmt6", "tsv"}:
        return parse_blast_outfmt6(text)
    if normalized == "paf":
        return parse_paf(text)
    if normalized == "gaf":
        return parse_gaf(text)
    raise ValueError("Alignment format must be blast6, paf, or gaf")


def attach_blast_hits(
    graph: GfaGraph,
    hits_by_query: Dict[str, List[Dict[str, Any]]],
    target_role: str = "query",
    source_name: str = "alignment",
) -> Dict[str, Any]:
    for segment in graph.segments.values():
        segment.blast_hits.clear()
    for link in graph.links:
        link.blast_hits.clear()

    matched = 0
    unmatched = 0
    total_hits = 0
    hits_by_target: Dict[str, List[Dict[str, Any]]] = {}
    for query_id, hits in hits_by_query.items():
        total_hits += len(hits)
        for hit in hits:
            normalized_hit = {**hit, "source": source_name}
            if target_role == "query":
                targets = [query_id]
            elif normalized_hit.get("format") == "gaf" and normalized_hit.get("pathSegments"):
                targets = list(dict.fromkeys(str(item) for item in normalized_hit["pathSegments"]))
            else:
                targets = [str(normalized_hit.get("sseqid") or "")]
            for target_id in targets:
                if target_id:
                    hits_by_target.setdefault(target_id, []).append(normalized_hit)

    for target_id, hits in hits_by_target.items():
        segment = graph.segments.get(target_id)
        if segment is None:
            unmatched += 1
            continue
        segment.blast_hits = sorted(
            hits,
            key=lambda hit: (
                hit.get("bitscore") or 0,
                hit.get("pident") or 0,
                hit.get("length") or hit.get("alnlen") or 0,
                hit.get("mapq") or 0,
            ),
            reverse=True,
        )
        matched += 1

    link_hits = attach_alignment_link_hits(graph, hits_by_query, target_role, source_name)
    return {
        "matched_queries": matched,
        "unmatched_queries": unmatched,
        "total_hits": total_hits,
        "matched_links": link_hits,
    }


def attach_alignment_link_hits(
    graph: GfaGraph,
    hits_by_query: Dict[str, List[Dict[str, Any]]],
    target_role: str,
    source_name: str,
) -> int:
    link_by_pair: Dict[frozenset[str], Link] = {}
    for link in graph.links:
        if link.source in graph.segments and link.target in graph.segments:
            link_by_pair.setdefault(frozenset([link.source, link.target]), link)

    matched_links = 0
    for query_id, hits in hits_by_query.items():
        if not hits:
            continue
        if any(hit.get("format") == "gaf" and hit.get("pathSegments") for hit in hits):
            paths = [hit.get("pathSegments") or [] for hit in hits]
        else:
            paths = [[_alignment_target_id(hit, query_id, target_role) for hit in _sort_hits_by_query_span(hits)]]
        for path in paths:
            clean_path = [segment_id for segment_id in path if segment_id in graph.segments]
            for source_id, target_id in zip(clean_path, clean_path[1:]):
                if source_id == target_id:
                    continue
                link = link_by_pair.get(frozenset([source_id, target_id]))
                if link is None:
                    continue
                link.blast_hits.append(
                    {
                        "format": "path",
                        "source": source_name,
                        "qseqid": query_id,
                        "sseqid": f"{source_id}->{target_id}",
                        "pathSegments": [source_id, target_id],
                        "pident": _average_hit_identity(hits),
                        "length": _sum_hit_lengths(hits),
                    }
                )
                matched_links += 1
    for link in graph.links:
        link.blast_hits.sort(
            key=lambda hit: (hit.get("pident") or 0, hit.get("length") or 0),
            reverse=True,
        )
    return matched_links


def _alignment_target_id(hit: Dict[str, Any], query_id: str, target_role: str) -> str:
    if target_role == "query":
        return str(query_id)
    return str(hit.get("sseqid") or "")


def _sort_hits_by_query_span(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(
        hits,
        key=lambda hit: (
            int(hit.get("qstart") or 0),
            int(hit.get("qend") or 0),
            str(hit.get("sseqid") or ""),
        ),
    )


def _average_hit_identity(hits: List[Dict[str, Any]]) -> Optional[float]:
    identities = [float(hit["pident"]) for hit in hits if hit.get("pident") is not None]
    if not identities:
        return None
    return sum(identities) / len(identities)


def _sum_hit_lengths(hits: List[Dict[str, Any]]) -> int:
    total = 0
    for hit in hits:
        try:
            total += int(hit.get("length") or hit.get("alnlen") or 0)
        except (TypeError, ValueError):
            continue
    return total
