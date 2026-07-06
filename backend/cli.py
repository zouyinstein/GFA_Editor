# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .cli_render import normalize_colour, render_graph
from .edit_history import build_history_document
from .gui_render import GuiRenderUnavailable, render_with_gui_export
from .gfa_core import (
    GfaGraph,
    attach_blast_hits,
    deduplicate_links,
    delete_edge,
    delete_node,
    delete_selection,
    duplicate_node,
    export_fasta,
    export_gfa,
    merge_link,
    merge_selection,
    parse_alignment_text,
    parse_gfa_lines,
    repeat_resolve_node,
    rotate_circular_node,
    update_edge,
    update_node,
)
from .graph_ops import (
    AutoRepeatCandidate,
    auto_repeat_ready_node_ids,
    build_auto_repeat_resolution_candidates,
    graph_is_circular_subgraph,
    graph_is_connected,
)
from .version import APP_VERSION


DEFAULT_AUTO_REPEAT_MAX_STATES = 5000
DEFAULT_AUTO_REPEAT_MAX_CANDIDATES = 100
DNA_COMPLEMENT = str.maketrans("ACGTRYKMSWBDHVNacgtrykmswbdhvn", "TGCAYRMKSWVHDBNtgcayrmkswvhdbn")
INVALID_DNA_BASE_RE = re.compile(r"[^ACGT]")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except BrokenPipeError:
        return 1
    except (FileNotFoundError, KeyError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"gfa-editor: error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gfa-editor",
        description="Command-line GFA Editor tools for drawing, repeat resolution, merging, export, and scripted edits.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {APP_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stats = subparsers.add_parser("stats", help="Print graph statistics")
    stats.add_argument("input", type=Path)
    stats.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    stats.set_defaults(func=cmd_stats)

    export = subparsers.add_parser("export", help="Export GFA or FASTA")
    export.add_argument("input", type=Path)
    export.add_argument("output", type=Path)
    export.add_argument("--format", choices=["gfa", "fasta", "fa"], help="Output format; defaults from extension")
    export.set_defaults(func=cmd_export)

    image = subparsers.add_parser("image", help="Draw a graph image like: bandage image graph.gfa graph.png")
    image.add_argument("input", type=Path)
    image.add_argument("output", type=Path)
    image.add_argument("--colour", "--color", default="depth", help="depth, blastsolid, random, degree, or solid")
    image.add_argument("--query", type=Path, help="FASTA query file; runs blastn/minimap2 when available, else exact-match fallback")
    image.add_argument("--alignment", type=Path, help="Precomputed BLAST outfmt6, PAF, or GAF alignment file")
    image.add_argument("--alignment-format", default="blast6", help="blast6, paf, or gaf for --alignment")
    image.add_argument("--alignment-tool", choices=["auto", "blastn", "minimap2", "exact"], default="auto")
    image.add_argument("--alignment-args", default="", help="Extra args for blastn/minimap2")
    image.add_argument("--target-role", choices=["subject", "query"], default="subject")
    image.add_argument("--layout", choices=["auto", "bandage", "bandage_native", "spring", "circle", "grid"], default="bandage")
    image.add_argument("--width", type=int, default=0, help="Output width in px/pt; defaults to GUI-style content bounds for bandage layout")
    image.add_argument("--height", type=int, default=0, help="Output height in px/pt; defaults to GUI-style content bounds for bandage layout")
    image.add_argument("--no-labels", action="store_true")
    image.set_defaults(func=cmd_image)

    auto_repeat = subparsers.add_parser("auto-repeat", aliases=["auto-repeat-resolution"], help="Search and apply automatic repeat resolution")
    auto_repeat.add_argument("input", type=Path)
    auto_repeat.add_argument("output", type=Path, nargs="?")
    add_auto_repeat_args(auto_repeat)
    auto_repeat.set_defaults(func=cmd_auto_repeat)

    merge = subparsers.add_parser("merge", help="Merge one link, a selected path/cycle, or all nodes")
    merge.add_argument("input", type=Path)
    merge.add_argument("output", type=Path)
    add_selection_args(merge)
    merge.add_argument("--all", action="store_true", help="Merge all contigs in the graph")
    merge.set_defaults(func=cmd_merge)

    auto_merge = subparsers.add_parser("auto-merge", help="Apply auto-repeat resolution, then merge the resolved circular graph")
    auto_merge.add_argument("input", type=Path)
    auto_merge.add_argument("output", type=Path)
    add_auto_repeat_args(auto_merge)
    auto_merge.add_argument("--resolved-output", type=Path, help="Optionally save the resolved intermediate GFA")
    auto_merge.set_defaults(func=cmd_auto_merge)

    delete = subparsers.add_parser("delete", help="Delete selected nodes and/or edges")
    delete.add_argument("input", type=Path)
    delete.add_argument("output", type=Path)
    add_selection_args(delete)
    delete.set_defaults(func=cmd_delete)

    duplicate = subparsers.add_parser("duplicate", help="Duplicate one node")
    duplicate.add_argument("input", type=Path)
    duplicate.add_argument("output", type=Path)
    duplicate.add_argument("node_id")
    duplicate.add_argument("--new-id")
    duplicate.set_defaults(func=cmd_duplicate)

    repeat = subparsers.add_parser("repeat", help="Apply manual repeat resolution after a node has been duplicated")
    repeat.add_argument("input", type=Path)
    repeat.add_argument("output", type=Path)
    repeat.add_argument("node_id")
    repeat.add_argument("duplicate_id")
    repeat.add_argument("--strategy", choices=["A", "B", "a", "b"], required=True)
    repeat.set_defaults(func=cmd_repeat)

    rotate = subparsers.add_parser("rotate", help="Rotate the start of a single circular contig")
    rotate.add_argument("input", type=Path)
    rotate.add_argument("output", type=Path)
    rotate.add_argument("node_id")
    rotate.add_argument("offset", type=int)
    rotate.set_defaults(func=cmd_rotate)

    update_node_parser = subparsers.add_parser("update-node", help="Rename or annotate a node")
    update_node_parser.add_argument("input", type=Path)
    update_node_parser.add_argument("output", type=Path)
    update_node_parser.add_argument("node_id")
    update_node_parser.add_argument("--name")
    update_node_parser.add_argument("--label")
    update_node_parser.add_argument("--color")
    update_node_parser.add_argument("--depth", type=float)
    update_node_parser.set_defaults(func=cmd_update_node)

    update_edge_parser = subparsers.add_parser("update-edge", help="Annotate an edge")
    update_edge_parser.add_argument("input", type=Path)
    update_edge_parser.add_argument("output", type=Path)
    update_edge_parser.add_argument("edge_id")
    update_edge_parser.add_argument("--label")
    update_edge_parser.add_argument("--color")
    update_edge_parser.add_argument("--support", type=float)
    update_edge_parser.add_argument("--cigar")
    update_edge_parser.set_defaults(func=cmd_update_edge)

    return parser


def add_auto_repeat_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--candidate",
        default=None,
        help="Candidate number or id to apply. Use 0 to write all candidates. Defaults to 1, or the best reference match with --reference-merged/--reference-fasta.",
    )
    parser.add_argument(
        "--reference-merged",
        type=Path,
        help="Choose the auto-repeat candidate whose merged sequence/order is closest to this merged GFA.",
    )
    parser.add_argument(
        "--reference-fasta",
        type=Path,
        help="Choose the auto-repeat candidate whose merged sequence is closest to this FASTA reference.",
    )
    parser.add_argument("--list-candidates", action="store_true", help="Print candidate summaries")
    parser.add_argument("--prefer-circular", action="store_true", default=False, help="Prefer circular candidates when choosing by number")
    parser.add_argument("--no-prefer-circular", action="store_false", dest="prefer_circular")
    parser.add_argument("--max-states", type=int, default=DEFAULT_AUTO_REPEAT_MAX_STATES)
    parser.add_argument("--max-candidates", type=int, default=DEFAULT_AUTO_REPEAT_MAX_CANDIDATES)
    parser.add_argument("--history-json", type=Path, help="Write the edit history used for the selected candidate")
    parser.add_argument("--summary-json", type=Path, help="Write JSON summary of the search and selected candidate")


def add_selection_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--node", dest="nodes", action="append", default=[], help="Selected node id; repeatable")
    parser.add_argument("--nodes", dest="nodes_csv", default="", help="Comma-separated selected node ids")
    parser.add_argument("--edge", dest="edges", action="append", default=[], help="Selected edge id; repeatable")
    parser.add_argument("--edges", dest="edges_csv", default="", help="Comma-separated selected edge ids")


def cmd_stats(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=False)
    stats = {
        **graph.stats(),
        "connected": graph_is_connected(graph),
        "circular": graph_is_circular_subgraph(graph),
        "auto_repeat_ready_nodes": auto_repeat_ready_node_ids(graph),
    }
    if args.json:
        print(json.dumps(stats, indent=2, sort_keys=True))
        return 0
    print(f"nodes: {stats['node_count']}")
    print(f"edges: {stats['edge_count']}")
    print(f"total_bp: {stats['total_bp']}")
    print(f"connected: {yes_no(stats['connected'])}")
    print(f"circular: {yes_no(stats['circular'])}")
    if stats["median_depth"] is not None:
        print(f"median_depth: {stats['median_depth']:.6g}")
    ready = stats["auto_repeat_ready_nodes"]
    print(f"auto_repeat_ready_nodes: {len(ready)}" + (f" ({', '.join(ready)})" if ready else ""))
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    fmt = output_format(args.output, args.format)
    graph = read_graph(args.input, keep_sequences=fmt in {"fasta", "fa"})
    body = export_fasta(graph) if fmt in {"fasta", "fa"} else export_gfa(graph)
    write_text(args.output, body)
    print(f"wrote {args.output}")
    return 0


def cmd_image(args: argparse.Namespace) -> int:
    colour = normalize_colour(args.colour)
    if should_use_gui_export(args):
        try:
            render_with_gui_export(
                args.input,
                args.output,
                colour=colour,
                show_labels=not args.no_labels,
                query_path=args.query,
                alignment_path=args.alignment,
                alignment_format=args.alignment_format,
                alignment_tool=args.alignment_tool,
                alignment_args=args.alignment_args,
                target_role=args.target_role,
            )
            print(f"wrote {args.output}")
            return 0
        except GuiRenderUnavailable as exc:
            print(f"warning: GUI export unavailable ({exc}); falling back to CLI renderer", file=sys.stderr)
    keep_sequences = bool(args.query)
    graph = read_graph(args.input, keep_sequences=keep_sequences)
    alignment_summary = None
    if args.alignment:
        hits_by_query = parse_alignment_text(args.alignment.read_text(encoding="utf-8", errors="replace"), args.alignment_format)
        alignment_summary = attach_blast_hits(graph, hits_by_query, target_role=args.target_role, source_name=str(args.alignment))
    elif args.query:
        hits_by_query, method = align_query_to_graph(
            graph,
            args.query,
            tool=args.alignment_tool,
            extra_args=args.alignment_args,
        )
        alignment_summary = attach_blast_hits(graph, hits_by_query, target_role="subject", source_name=f"{method}:{args.query.name}")
        print(f"alignment: {method}, hits={alignment_summary.get('total_hits', 0)}, matched={alignment_summary.get('matched_queries', 0)}")
    elif colour == "blastsolid":
        print("warning: --colour blastsolid was requested without --query or --alignment; all graph items are unhit", file=sys.stderr)

    render_graph(
        graph,
        args.output,
        width=args.width,
        height=args.height,
        layout=args.layout,
        colour=colour,
        show_labels=not args.no_labels,
        title=args.input.name,
    )
    print(f"wrote {args.output}")
    return 0


def should_use_gui_export(args: argparse.Namespace) -> bool:
    layout = str(getattr(args, "layout", "") or "").strip().lower().replace("-", "_")
    if layout not in {"auto", "bandage", "bandage_native", "band"}:
        return False
    query = getattr(args, "query", None)
    alignment = getattr(args, "alignment", None)
    alignment_tool = str(getattr(args, "alignment_tool", "") or "").strip().lower()
    if query and alignment_tool == "exact":
        return False
    if int(getattr(args, "width", 0) or 0) > 0 or int(getattr(args, "height", 0) or 0) > 0:
        return False
    if Path(args.output).suffix.lower() not in {".pdf", ".svg"}:
        return False
    return True


def cmd_auto_repeat(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    candidates, warning = build_auto_repeat_resolution_candidates(
        graph,
        max_states=max(1, args.max_states),
        max_candidates=max(1, args.max_candidates),
    )
    reference_selection = score_candidates_against_reference_args(candidates, args)
    if args.list_candidates:
        print_candidate_summaries(candidates, warning, reference_selection=reference_selection)
    if not candidates:
        if args.output:
            raise ValueError(warning or "No auto repeat resolution candidates were found")
        return 1
    if not args.output:
        if args.list_candidates:
            return 0
        raise ValueError("Output GFA is required unless --list-candidates is used")
    if wants_all_candidates(args):
        written_paths = write_all_resolved_candidates(args.output, candidates)
        write_optional_auto_repeat_reports(
            args,
            candidates,
            None,
            warning,
            args.input,
            reference_selection=reference_selection,
        )
        print(f"wrote {len(written_paths)} resolved candidates")
        for path in written_paths:
            print(f"wrote {path}")
        return 0
    selected = choose_auto_repeat_candidate(candidates, args, reference_selection)
    write_graph(args.output, selected.graph)
    write_optional_auto_repeat_reports(
        args,
        candidates,
        selected,
        warning,
        args.input,
        reference_selection=reference_selection,
    )
    print_reference_selection(args, reference_selection, selected)
    print(f"selected {selected.id}: {len(selected.graph.segments)} nodes, {len(selected.graph.links)} links")
    print(f"wrote {args.output}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    node_ids, edge_ids = selected_ids(args)
    if args.all or (not node_ids and not edge_ids):
        node_ids = list(graph.segments)
    if len(node_ids) < 2 and len(edge_ids) == 1:
        result = merge_link(graph, edge_ids[0])
    else:
        result = merge_selection(graph, node_ids, edge_ids)
    deduplicate_links(graph)
    write_graph(args.output, graph)
    print(f"merged: {result.get('new_node_id') or result.get('edge_id')}")
    print(f"wrote {args.output}")
    return 0


def cmd_auto_merge(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    candidates, warning = build_auto_repeat_resolution_candidates(
        graph,
        max_states=max(1, args.max_states),
        max_candidates=max(1, args.max_candidates),
    )
    reference_selection = score_candidates_against_reference_args(candidates, args)
    if args.list_candidates:
        print_candidate_summaries(candidates, warning, reference_selection=reference_selection)
    if not candidates:
        raise ValueError(warning or "No auto repeat resolution candidates were found")
    if wants_all_candidates(args):
        written_paths = write_all_merged_candidates(args.output, candidates, resolved_output=args.resolved_output)
        write_optional_auto_repeat_reports(
            args,
            candidates,
            None,
            warning,
            args.input,
            reference_selection=reference_selection,
        )
        print(f"wrote {len(written_paths)} merged candidates")
        for path in written_paths:
            print(f"wrote {path}")
        return 0
    selected = choose_auto_repeat_candidate(candidates, args, reference_selection)
    resolved_graph = selected.graph.clone()
    if args.resolved_output:
        write_graph(args.resolved_output, resolved_graph)
        print(f"wrote {args.resolved_output}")
    merge_result = merge_all_nodes(resolved_graph)
    write_graph(args.output, resolved_graph)
    write_optional_auto_repeat_reports(
        args,
        candidates,
        selected,
        warning,
        args.input,
        reference_selection=reference_selection,
    )
    print_reference_selection(args, reference_selection, selected)
    print(f"selected {selected.id}; merged into {merge_result.get('new_node_id')}")
    print(f"wrote {args.output}")
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    node_ids, edge_ids = selected_ids(args)
    if node_ids and not edge_ids:
        for node_id in node_ids:
            delete_node(graph, node_id)
        result = {"removed_nodes": len(node_ids)}
    elif edge_ids and not node_ids:
        for edge_id in edge_ids:
            delete_edge(graph, edge_id)
        result = {"removed_edges": len(edge_ids)}
    else:
        result = delete_selection(graph, node_ids, edge_ids)
    deduplicate_links(graph)
    write_graph(args.output, graph)
    print(json.dumps(result, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


def cmd_duplicate(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    result = duplicate_node(graph, args.node_id, args.new_id)
    deduplicate_links(graph)
    write_graph(args.output, graph)
    print(json.dumps(result, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


def cmd_repeat(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    result = repeat_resolve_node(graph, args.node_id, args.duplicate_id, args.strategy)
    deduplicate_links(graph)
    write_graph(args.output, graph)
    print(json.dumps(result, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


def cmd_rotate(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    result = rotate_circular_node(graph, args.node_id, args.offset)
    write_graph(args.output, graph)
    print(json.dumps(result, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


def cmd_update_node(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    result = update_node(
        graph,
        args.node_id,
        name=args.name,
        label=args.label,
        color=args.color,
        depth=args.depth,
    )
    deduplicate_links(graph)
    write_graph(args.output, graph)
    print(json.dumps(result, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


def cmd_update_edge(args: argparse.Namespace) -> int:
    graph = read_graph(args.input, keep_sequences=True)
    result = update_edge(
        graph,
        args.edge_id,
        label=args.label,
        color=args.color,
        support=args.support,
        cigar=args.cigar,
    )
    deduplicate_links(graph)
    write_graph(args.output, graph)
    print(json.dumps(result, sort_keys=True))
    print(f"wrote {args.output}")
    return 0


def read_graph(path: Path, *, keep_sequences: bool) -> GfaGraph:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("rb") as handle:
        graph = parse_gfa_lines(handle, keep_sequences=keep_sequences)
    deduplicate_links(graph)
    return graph


def write_graph(path: Path, graph: GfaGraph) -> None:
    write_text(path, export_gfa(graph))


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def output_format(output: Path, explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    suffix = output.suffix.lower()
    if suffix in {".fa", ".fasta", ".fna"}:
        return "fasta"
    return "gfa"


def selected_ids(args: argparse.Namespace) -> Tuple[List[str], List[str]]:
    nodes = unique_ids([*args.nodes, *split_ids(args.nodes_csv)])
    edges = unique_ids([*args.edges, *split_ids(args.edges_csv)])
    return nodes, edges


def split_ids(value: str) -> List[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def unique_ids(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def print_candidate_summaries(
    candidates: List[AutoRepeatCandidate],
    warning: Optional[str],
    *,
    reference_selection: Optional[Dict[str, Any]] = None,
) -> None:
    score_by_id = {
        item["candidate"]: item
        for item in (reference_selection or {}).get("scores", [])
    }
    for index, candidate in enumerate(candidates, start=1):
        order = " ".join(f"{item['nodeId']}:{item['strategy']}" for item in candidate.order)
        circular = " circular" if candidate.circular else ""
        score_payload = score_by_id.get(candidate.id)
        score_text = f"\treference_score={score_payload['score']:.6g}" if score_payload else ""
        print(
            f"{index}\t{candidate.id}\t{len(candidate.graph.segments)} nodes\t"
            f"{len(candidate.graph.links)} links\t{len(candidate.steps)} steps{circular}\t{order}{score_text}"
        )
    if warning:
        print(f"warning: {warning}", file=sys.stderr)


def select_candidate(
    candidates: List[AutoRepeatCandidate],
    selector: str,
    *,
    prefer_circular: bool,
) -> AutoRepeatCandidate:
    if not candidates:
        raise ValueError("No candidates are available")
    pool = candidates
    if prefer_circular and any(candidate.circular for candidate in candidates):
        pool = [candidate for candidate in candidates if candidate.circular]
    cleaned = str(selector or "1").strip()
    for candidate in candidates:
        if candidate.id == cleaned:
            return candidate
    try:
        index = int(cleaned)
    except ValueError as exc:
        raise ValueError(f"Unknown candidate: {selector}") from exc
    if index < 1 or index > len(pool):
        raise ValueError(f"Candidate number out of range: {index}")
    return pool[index - 1]


def candidate_selector(args: argparse.Namespace) -> Optional[str]:
    value = getattr(args, "candidate", None)
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def wants_all_candidates(args: argparse.Namespace) -> bool:
    return candidate_selector(args) == "0"


def choose_auto_repeat_candidate(
    candidates: List[AutoRepeatCandidate],
    args: argparse.Namespace,
    reference_selection: Optional[Dict[str, Any]],
) -> AutoRepeatCandidate:
    selector = candidate_selector(args)
    if selector is None and reference_selection is not None:
        best = reference_selection.get("best")
        if best:
            candidate_id = best["candidate"]
            for candidate in candidates:
                if candidate.id == candidate_id:
                    return candidate
    return select_candidate(candidates, selector or "1", prefer_circular=args.prefer_circular)


def print_reference_selection(
    args: argparse.Namespace,
    reference_selection: Optional[Dict[str, Any]],
    selected: AutoRepeatCandidate,
) -> None:
    if candidate_selector(args) is not None or reference_selection is None:
        return
    best = reference_selection.get("best")
    if not best or best.get("candidate") != selected.id:
        return
    record_text = f", record={best.get('referenceRecord')}" if best.get("referenceRecord") else ""
    print(
        "reference-selected "
        f"{selected.id}: score={best['score']:.6g}, method={best.get('method', 'unknown')}, "
        f"reference={reference_selection.get('path')}{record_text}"
    )


def candidate_path(base_path: Path, candidate: AutoRepeatCandidate, *, default_suffix: str = ".gfa") -> Path:
    if base_path.exists() and base_path.is_dir():
        return base_path / f"{candidate.id}{default_suffix}"
    if base_path.suffix:
        return base_path.with_name(f"{base_path.stem}.{candidate.id}{base_path.suffix}")
    return base_path / f"{candidate.id}{default_suffix}"


def write_all_resolved_candidates(base_output: Path, candidates: List[AutoRepeatCandidate]) -> List[Path]:
    paths = []
    for candidate in candidates:
        output_path = candidate_path(base_output, candidate, default_suffix=".gfa")
        write_graph(output_path, candidate.graph)
        paths.append(output_path)
    return paths


def write_all_merged_candidates(
    base_output: Path,
    candidates: List[AutoRepeatCandidate],
    *,
    resolved_output: Optional[Path],
) -> List[Path]:
    paths = []
    for candidate in candidates:
        merged_graph = candidate.graph.clone()
        if resolved_output:
            write_graph(candidate_path(resolved_output, candidate, default_suffix=".gfa"), merged_graph)
        merge_all_nodes(merged_graph)
        output_path = candidate_path(base_output, candidate, default_suffix=".gfa")
        write_graph(output_path, merged_graph)
        paths.append(output_path)
    return paths


def merge_all_nodes(graph: GfaGraph) -> Dict[str, Any]:
    if len(graph.segments) < 2:
        deduplicate_links(graph)
        node_id = next(iter(graph.segments), None)
        return {"new_node_id": node_id, "node_ids": [node_id] if node_id else [], "merged_steps": []}
    result = merge_selection(graph, list(graph.segments), [])
    deduplicate_links(graph)
    return result


def write_optional_auto_repeat_reports(
    args: argparse.Namespace,
    candidates: List[AutoRepeatCandidate],
    selected: Optional[AutoRepeatCandidate],
    warning: Optional[str],
    source_path: Path,
    *,
    reference_selection: Optional[Dict[str, Any]] = None,
) -> None:
    if getattr(args, "history_json", None):
        if selected is not None:
            history = build_history_document(selected.steps, source_name=str(source_path), warnings=[warning] if warning else [])
            write_text(args.history_json, json.dumps(history, indent=2, sort_keys=True) + "\n")
        else:
            for candidate in candidates:
                history = build_history_document(candidate.steps, source_name=str(source_path), warnings=[warning] if warning else [])
                write_text(
                    candidate_path(args.history_json, candidate, default_suffix=".json"),
                    json.dumps(history, indent=2, sort_keys=True) + "\n",
                )
    if getattr(args, "summary_json", None):
        payload = {
            "source": str(source_path),
            "warning": warning,
            "selected": selected.summary() if selected is not None else None,
            "candidate_count": len(candidates),
            "candidates": [candidate.summary() for candidate in candidates],
        }
        if reference_selection is not None:
            payload["reference_selection"] = reference_selection
        write_text(args.summary_json, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def score_candidates_against_reference_args(
    candidates: List[AutoRepeatCandidate],
    args: argparse.Namespace,
) -> Optional[Dict[str, Any]]:
    if getattr(args, "reference_merged", None) and getattr(args, "reference_fasta", None):
        raise ValueError("Use only one of --reference-merged or --reference-fasta")
    if getattr(args, "reference_merged", None):
        return score_candidates_against_reference_merged(candidates, args.reference_merged)
    if getattr(args, "reference_fasta", None):
        return score_candidates_against_reference_fasta(candidates, args.reference_fasta)
    return None


def score_candidates_against_reference_merged(
    candidates: List[AutoRepeatCandidate],
    reference_path: Path,
) -> Dict[str, Any]:
    if not reference_path.is_file():
        raise FileNotFoundError(reference_path)
    reference_graph = read_graph(reference_path, keep_sequences=True)
    merge_all_nodes(reference_graph)
    reference = graph_arrangement(reference_graph)
    reference_indexes = build_reference_sequence_indexes(reference.get("sequence"))
    scores = []
    for candidate_index, candidate in enumerate(candidates):
        candidate_graph = candidate.graph.clone()
        merge_all_nodes(candidate_graph)
        arrangement = graph_arrangement(candidate_graph)
        score = score_arrangement(arrangement, reference, reference_indexes=reference_indexes)
        scores.append(
            {
                "candidate": candidate.id,
                "candidateIndex": candidate_index + 1,
                **score,
            }
        )
    best = None
    if scores:
        best = max(
            scores,
            key=lambda item: (
                float(item.get("score", 0.0)),
                float(item.get("continuousFraction", 0.0)),
                float(item.get("diagonalFraction", 0.0)),
                -int(item.get("lengthDelta", 0)),
                -int(item.get("candidateIndex", 0)),
            ),
        )
    return {
        "type": "merged-gfa",
        "path": str(reference_path),
        "reference": arrangement_metadata(reference),
        "best": best,
        "scores": scores,
    }


def score_candidates_against_reference_fasta(
    candidates: List[AutoRepeatCandidate],
    reference_path: Path,
) -> Dict[str, Any]:
    if not reference_path.is_file():
        raise FileNotFoundError(reference_path)
    records = parse_fasta(reference_path.read_text(encoding="utf-8", errors="replace"))
    if not records:
        raise ValueError(f"No FASTA records found in {reference_path}")
    references = [
        {
            "record": record_id,
            "arrangement": fasta_arrangement(record_id, sequence),
        }
        for record_id, sequence in records
    ]
    for reference in references:
        reference["indexes"] = build_reference_sequence_indexes(reference["arrangement"].get("sequence"))

    scores = []
    for candidate_index, candidate in enumerate(candidates):
        candidate_graph = candidate.graph.clone()
        merge_all_nodes(candidate_graph)
        arrangement = graph_arrangement(candidate_graph)
        best_score = None
        for reference in references:
            score = score_arrangement(
                arrangement,
                reference["arrangement"],
                reference_indexes=reference["indexes"],
            )
            score = {
                "referenceRecord": reference["record"],
                **score,
            }
            if best_score is None or reference_score_key(score, candidate_index) > reference_score_key(best_score, candidate_index):
                best_score = score
        scores.append(
            {
                "candidate": candidate.id,
                "candidateIndex": candidate_index + 1,
                **(best_score or {}),
            }
        )
    best = best_reference_score(scores)
    return {
        "type": "fasta",
        "path": str(reference_path),
        "reference": {
            "record_count": len(references),
            "records": [
                {
                    "id": reference["record"],
                    **arrangement_metadata(reference["arrangement"]),
                }
                for reference in references
            ],
        },
        "best": best,
        "scores": scores,
    }


def best_reference_score(scores: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not scores:
        return None
    return max(
        scores,
        key=lambda item: (
            float(item.get("score", 0.0)),
            float(item.get("continuousFraction", 0.0)),
            float(item.get("diagonalFraction", 0.0)),
            -int(item.get("lengthDelta", 0)),
            -int(item.get("candidateIndex", 0)),
        ),
    )


def reference_score_key(score: Dict[str, Any], candidate_index: int) -> Tuple[float, float, float, int, int]:
    return (
        float(score.get("score", 0.0)),
        float(score.get("continuousFraction", 0.0)),
        float(score.get("diagonalFraction", 0.0)),
        -int(score.get("lengthDelta", 0)),
        -candidate_index,
    )


def graph_arrangement(graph: GfaGraph) -> Dict[str, Any]:
    segment = next(iter(graph.segments.values()), None)
    node_id = segment.id if segment is not None else ""
    sequence = segment.sequence.upper() if segment is not None and segment.sequence else None
    return {
        "node_id": node_id,
        "sequence": sequence,
        "length": len(sequence) if sequence is not None else (segment.length if segment is not None else 0),
        "tokens": tokenize_merged_node_id(node_id),
    }


def fasta_arrangement(record_id: str, sequence: str) -> Dict[str, Any]:
    cleaned_sequence = "".join(str(sequence or "").split()).upper()
    return {
        "node_id": record_id,
        "sequence": cleaned_sequence,
        "length": len(cleaned_sequence),
        "tokens": tokenize_merged_node_id(record_id),
    }


def arrangement_metadata(arrangement: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "node_id": arrangement.get("node_id", ""),
        "length": arrangement.get("length", 0),
        "token_count": len(arrangement.get("tokens") or []),
        "has_sequence": bool(arrangement.get("sequence")),
    }


def score_arrangement(
    candidate: Dict[str, Any],
    reference: Dict[str, Any],
    *,
    reference_indexes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    candidate_sequence = candidate.get("sequence")
    reference_sequence = reference.get("sequence")
    if candidate_sequence and reference_sequence:
        sequence_score = score_sequence_arrangement(candidate_sequence, reference_sequence, reference_indexes)
        if sequence_score["score"] > 0:
            return {
                **sequence_score,
                "lengthDelta": abs(len(candidate_sequence) - len(reference_sequence)),
            }
    token_score = score_token_arrangement(candidate.get("tokens") or [], reference.get("tokens") or [])
    token_score["lengthDelta"] = abs(int(candidate.get("length", 0)) - int(reference.get("length", 0)))
    return token_score


def score_sequence_arrangement(
    candidate_sequence: str,
    reference_sequence: str,
    reference_indexes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    exact_match = exact_circular_sequence_score(candidate_sequence, reference_sequence)
    if exact_match is not None:
        return exact_match
    best: Dict[str, Any] = {
        "score": 0.0,
        "method": "sequence-global-kmer-chain",
        "orientation": "+",
        "kmer": None,
        "sampledKmers": 0,
        "matchedKmers": 0,
        "bestDiagonalCount": 0,
        "globalChainKmers": 0,
        "globalChainBp": 0,
        "globalChainFraction": 0.0,
        "continuousBp": 0,
        "continuousFraction": 0.0,
        "diagonalFraction": 0.0,
    }
    if reference_indexes is None:
        reference_indexes = build_reference_sequence_indexes(reference_sequence)
    for reference_payload in reference_indexes:
        kmer_size = int(reference_payload["kmer"])
        if len(candidate_sequence) < kmer_size:
            continue
        reference_index = reference_payload["index"]
        if not reference_index:
            continue
        for orientation, oriented_sequence in (
            ("+", candidate_sequence),
            ("-", reverse_complement(candidate_sequence)),
        ):
            score = global_kmer_chain_score(oriented_sequence, reference_sequence, reference_index, kmer_size)
            score["orientation"] = orientation
            if (
                score["score"] > best["score"]
                or (
                    score["score"] == best["score"]
                    and float(score.get("continuousFraction", 0.0)) > float(best.get("continuousFraction", 0.0))
                )
                or (
                    score["score"] == best["score"]
                    and float(score.get("continuousFraction", 0.0)) == float(best.get("continuousFraction", 0.0))
                    and orientation == "+"
                    and best.get("orientation") != "+"
                )
            ):
                best = score
        if best["score"] > 0:
            break
    return best


def exact_circular_sequence_score(candidate_sequence: str, reference_sequence: str) -> Optional[Dict[str, Any]]:
    if len(candidate_sequence) != len(reference_sequence) or not candidate_sequence:
        return None
    doubled_reference = reference_sequence + reference_sequence
    if candidate_sequence in doubled_reference:
        return {
            "score": 1.0,
            "method": "sequence-exact-circular",
            "orientation": "+",
            "kmer": None,
            "sampledKmers": 0,
            "matchedKmers": 0,
            "bestDiagonalCount": 0,
            "continuousBp": len(candidate_sequence),
            "continuousFraction": 1.0,
            "diagonalFraction": 1.0,
        }
    reverse_candidate = reverse_complement(candidate_sequence)
    if reverse_candidate in doubled_reference:
        return {
            "score": 1.0,
            "method": "sequence-exact-circular",
            "orientation": "-",
            "kmer": None,
            "sampledKmers": 0,
            "matchedKmers": 0,
            "bestDiagonalCount": 0,
            "continuousBp": len(candidate_sequence),
            "continuousFraction": 1.0,
            "diagonalFraction": 1.0,
        }
    return None


def build_reference_sequence_indexes(sequence: Optional[str]) -> List[Dict[str, Any]]:
    if not sequence:
        return []
    indexes = []
    for kmer_size in (31, 21, 15, 11):
        if len(sequence) < kmer_size:
            continue
        indexes.append(
            {
                "kmer": kmer_size,
                "index": build_circular_kmer_index(sequence, kmer_size),
            }
        )
    return indexes


def build_circular_kmer_index(sequence: str, kmer_size: int) -> Dict[str, List[int]]:
    index: Dict[str, List[int]] = {}
    sequence_length = len(sequence)
    if sequence_length < kmer_size:
        return index
    stride = max(1, sequence_length // 500000)
    for position in range(0, sequence_length, stride):
        kmer = circular_kmer(sequence, position, kmer_size)
        if not valid_dna_kmer(kmer):
            continue
        positions = index.setdefault(kmer, [])
        if len(positions) <= 50:
            positions.append(position)
    return index


def circular_kmer(sequence: str, position: int, kmer_size: int) -> str:
    end = position + kmer_size
    if end <= len(sequence):
        return sequence[position:end]
    return sequence[position:] + sequence[: end - len(sequence)]


def continuous_kmer_score(
    candidate_sequence: str,
    reference_sequence: str,
    reference_index: Dict[str, List[int]],
    kmer_size: int,
) -> Dict[str, Any]:
    reference_length = len(reference_sequence)
    candidate_limit = len(candidate_sequence) - kmer_size + 1
    stride = max(1, len(candidate_sequence) // 5000)
    bin_size = max(25, reference_length // 5000)
    sampled = 0
    matched = 0
    diagonal_bins: Counter[int] = Counter()
    positions_by_bin: Dict[int, List[int]] = {}
    for query_position in range(0, max(0, candidate_limit), stride):
        kmer = candidate_sequence[query_position : query_position + kmer_size]
        if not valid_dna_kmer(kmer):
            continue
        sampled += 1
        reference_positions = reference_index.get(kmer)
        if not reference_positions or len(reference_positions) > 50:
            continue
        matched += 1
        for reference_position in reference_positions:
            diagonal = (reference_position - query_position) % reference_length
            diagonal_bin = diagonal // bin_size
            diagonal_bins[diagonal_bin] += 1
            positions_by_bin.setdefault(diagonal_bin, []).append(query_position)
    best_diagonal_count = max(diagonal_bins.values()) if diagonal_bins else 0
    best_bin = diagonal_bins.most_common(1)[0][0] if diagonal_bins else None
    continuous_bp, continuous_kmers = longest_continuous_kmer_chain(
        positions_by_bin.get(best_bin, []) if best_bin is not None else [],
        kmer_size,
        stride,
    )
    continuous_fraction = continuous_bp / max(len(candidate_sequence), len(reference_sequence), 1)
    diagonal_fraction = best_diagonal_count / sampled if sampled else 0.0
    score = (0.9 * continuous_fraction) + (0.1 * diagonal_fraction)
    return {
        "score": score,
        "method": f"sequence-continuous-kmer-{kmer_size}",
        "kmer": kmer_size,
        "sampledKmers": sampled,
        "matchedKmers": matched,
        "bestDiagonalCount": best_diagonal_count,
        "bestDiagonalBin": best_bin,
        "diagonalBinSize": bin_size,
        "diagonalFraction": diagonal_fraction,
        "continuousBp": continuous_bp,
        "continuousKmers": continuous_kmers,
        "continuousFraction": continuous_fraction,
    }


def global_kmer_chain_score(
    candidate_sequence: str,
    reference_sequence: str,
    reference_index: Dict[str, List[int]],
    kmer_size: int,
) -> Dict[str, Any]:
    reference_length = len(reference_sequence)
    candidate_limit = len(candidate_sequence) - kmer_size + 1
    stride = max(1, len(candidate_sequence) // 5000)
    bin_size = max(25, reference_length // 5000) if reference_length else 25
    sampled = 0
    matched = 0
    diagonal_bins: Counter[int] = Counter()
    anchors: List[Tuple[int, int, int]] = []
    reference_copies = max(2, (len(candidate_sequence) // max(reference_length, 1)) + 2)
    for query_position in range(0, max(0, candidate_limit), stride):
        kmer = candidate_sequence[query_position : query_position + kmer_size]
        if not valid_dna_kmer(kmer):
            continue
        sampled += 1
        reference_positions = reference_index.get(kmer)
        if not reference_positions or len(reference_positions) > 50:
            continue
        matched += 1
        for reference_position in reference_positions:
            diagonal = (reference_position - query_position) % reference_length
            diagonal_bin = diagonal // bin_size
            diagonal_bins[diagonal_bin] += 1
            for copy_index in range(reference_copies):
                unwrapped_reference_position = reference_position + (copy_index * reference_length)
                anchors.append((query_position, unwrapped_reference_position, reference_position))

    chain = longest_global_kmer_chain(anchors, kmer_size)
    chain_kmers = len(chain)
    if chain_kmers:
        chain_bp = min(len(candidate_sequence), ((chain_kmers - 1) * stride) + kmer_size)
        query_start = chain[0][0]
        query_end = chain[-1][0] + kmer_size
        reference_start = chain[0][1]
        reference_end = chain[-1][1] + kmer_size
    else:
        chain_bp = 0
        query_start = None
        query_end = None
        reference_start = None
        reference_end = None
    best_diagonal_count = max(diagonal_bins.values()) if diagonal_bins else 0
    best_bin = diagonal_bins.most_common(1)[0][0] if diagonal_bins else None
    chain_fraction = chain_kmers / sampled if sampled else 0.0
    continuous_fraction = chain_bp / max(len(candidate_sequence), len(reference_sequence), 1)
    diagonal_fraction = best_diagonal_count / sampled if sampled else 0.0
    return {
        "score": chain_fraction,
        "method": f"sequence-global-kmer-chain-{kmer_size}",
        "kmer": kmer_size,
        "sampledKmers": sampled,
        "matchedKmers": matched,
        "bestDiagonalCount": best_diagonal_count,
        "bestDiagonalBin": best_bin,
        "diagonalBinSize": bin_size,
        "diagonalFraction": diagonal_fraction,
        "globalChainKmers": chain_kmers,
        "globalChainBp": chain_bp,
        "globalChainFraction": chain_fraction,
        "globalChainQueryStart": query_start,
        "globalChainQueryEnd": query_end,
        "globalChainReferenceStart": reference_start,
        "globalChainReferenceEnd": reference_end,
        "continuousBp": chain_bp,
        "continuousKmers": chain_kmers,
        "continuousFraction": continuous_fraction,
    }


def longest_global_kmer_chain(
    anchors: List[Tuple[int, int, int]],
    kmer_size: int,
) -> List[Tuple[int, int, int]]:
    if not anchors:
        return []
    sorted_anchors = sorted(set(anchors))
    reference_coordinates = sorted({anchor[1] for anchor in sorted_anchors})
    coordinate_rank = {coordinate: index + 1 for index, coordinate in enumerate(reference_coordinates)}
    states: List[Tuple[int, int, int, int, int, int, int, int, int]] = []
    tree = [-1] * (len(reference_coordinates) + 1)

    def state_key(index: int) -> Tuple[int, int, int, int, int]:
        if index < 0:
            return (0, 0, 0, 0, 0)
        count, query_start, query_end, reference_start, reference_end, *_ = states[index]
        return (
            count,
            query_end - query_start + kmer_size,
            reference_end - reference_start + kmer_size,
            -query_start,
            -reference_start,
        )

    def better(left: int, right: int) -> int:
        return left if state_key(left) >= state_key(right) else right

    def update(rank: int, state_index: int) -> None:
        while rank < len(tree):
            tree[rank] = better(state_index, tree[rank])
            rank += rank & -rank

    def query(rank: int) -> int:
        best = -1
        while rank > 0:
            best = better(best, tree[rank])
            rank -= rank & -rank
        return best

    index = 0
    best_state = -1
    while index < len(sorted_anchors):
        query_position = sorted_anchors[index][0]
        group_updates: List[Tuple[int, int]] = []
        while index < len(sorted_anchors) and sorted_anchors[index][0] == query_position:
            query_pos, reference_pos, reference_mod_pos = sorted_anchors[index]
            rank = coordinate_rank[reference_pos]
            predecessor = query(rank - 1)
            if predecessor >= 0:
                count, query_start, _, reference_start, _, *_ = states[predecessor]
                state = (
                    count + 1,
                    query_start,
                    query_pos,
                    reference_start,
                    reference_pos,
                    predecessor,
                    query_pos,
                    reference_pos,
                    reference_mod_pos,
                )
            else:
                state = (
                    1,
                    query_pos,
                    query_pos,
                    reference_pos,
                    reference_pos,
                    -1,
                    query_pos,
                    reference_pos,
                    reference_mod_pos,
                )
            state_index = len(states)
            states.append(state)
            group_updates.append((rank, state_index))
            best_state = better(state_index, best_state)
            index += 1
        for rank, state_index in group_updates:
            update(rank, state_index)

    chain: List[Tuple[int, int, int]] = []
    state_index = best_state
    while state_index >= 0:
        state = states[state_index]
        chain.append((state[6], state[7], state[8]))
        state_index = state[5]
    chain.reverse()
    return chain


def longest_continuous_kmer_chain(positions: List[int], kmer_size: int, stride: int) -> Tuple[int, int]:
    if not positions:
        return 0, 0
    unique_positions = sorted(set(positions))
    allowed_gap = max(kmer_size * 40, stride * 100, 5000)
    best_bp = kmer_size
    best_count = 1
    current_start = unique_positions[0]
    current_previous = unique_positions[0]
    current_count = 1
    for position in unique_positions[1:]:
        if position - current_previous <= allowed_gap:
            current_previous = position
            current_count += 1
        else:
            current_bp = current_previous - current_start + kmer_size
            if current_bp > best_bp:
                best_bp = current_bp
                best_count = current_count
            current_start = position
            current_previous = position
            current_count = 1
    current_bp = current_previous - current_start + kmer_size
    if current_bp > best_bp:
        best_bp = current_bp
        best_count = current_count
    return best_bp, best_count


def valid_dna_kmer(kmer: str) -> bool:
    return bool(kmer) and INVALID_DNA_BASE_RE.search(kmer) is None


def tokenize_merged_node_id(node_id: str) -> List[str]:
    tokens: List[str] = []
    for part in (piece for piece in node_id.split("_") if piece):
        if re.fullmatch(r"copy\d+", part) and tokens:
            tokens[-1] = f"{tokens[-1]}_{part}"
        else:
            tokens.append(part)
    return tokens


def score_token_arrangement(candidate_tokens: List[str], reference_tokens: List[str]) -> Dict[str, Any]:
    if not candidate_tokens or not reference_tokens:
        return {
            "score": 0.0,
            "method": "token-lcs",
            "orientation": "+",
            "matchedTokens": 0,
            "referenceTokens": len(reference_tokens),
            "candidateTokens": len(candidate_tokens),
        }
    forward = circular_token_lcs_score(candidate_tokens, reference_tokens)
    reverse = circular_token_lcs_score(list(reversed(candidate_tokens)), reference_tokens)
    if reverse > forward:
        score = reverse
        orientation = "-"
    else:
        score = forward
        orientation = "+"
    matched_tokens = int(round(score * max(len(candidate_tokens), len(reference_tokens))))
    return {
        "score": score,
        "method": "token-lcs",
        "orientation": orientation,
        "matchedTokens": matched_tokens,
        "referenceTokens": len(reference_tokens),
        "candidateTokens": len(candidate_tokens),
    }


def circular_token_lcs_score(candidate_tokens: List[str], reference_tokens: List[str]) -> float:
    denominator = max(len(candidate_tokens), len(reference_tokens), 1)
    best = 0
    for offset in range(len(reference_tokens)):
        rotated = reference_tokens[offset:] + reference_tokens[:offset]
        best = max(best, lcs_length(candidate_tokens, rotated))
    return best / denominator


def lcs_length(left: List[str], right: List[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def align_query_to_graph(
    graph: GfaGraph,
    query_path: Path,
    *,
    tool: str,
    extra_args: str,
) -> Tuple[Dict[str, List[Dict[str, Any]]], str]:
    if not query_path.is_file():
        raise FileNotFoundError(query_path)
    requested = tool.lower()
    if requested == "exact":
        return exact_query_hits(graph, query_path), "exact"
    if requested in {"auto", "blastn"} and shutil.which("blastn"):
        return run_alignment_tool(graph, query_path, "blastn", extra_args), "blastn"
    if requested in {"auto", "minimap2"} and shutil.which("minimap2"):
        return run_alignment_tool(graph, query_path, "minimap2", extra_args), "minimap2"
    if requested != "auto":
        raise RuntimeError(f"{requested} is not installed or not on PATH")
    hits = exact_query_hits(graph, query_path)
    if not any(hits.values()):
        print("warning: blastn/minimap2 not found; exact query fallback found no hits", file=sys.stderr)
    return hits, "exact"


def run_alignment_tool(
    graph: GfaGraph,
    query_path: Path,
    tool: str,
    extra_args: str,
) -> Dict[str, List[Dict[str, Any]]]:
    target_text = export_fasta(graph)
    with tempfile.TemporaryDirectory(prefix="gfa-editor-cli-align-") as tmp:
        tmpdir = Path(tmp)
        target_path = tmpdir / "graph.fa"
        output_path = tmpdir / "alignment.out"
        target_path.write_text(target_text, encoding="utf-8")
        args = shlex.split(extra_args) if extra_args.strip() else []
        if tool == "blastn":
            args = strip_arg_values(args, {"-out", "-outfmt", "-query", "-subject"})
            if not args:
                args = ["-task", "megablast", "-evalue", "1e-10", "-perc_identity", "80", "-max_target_seqs", "25"]
            command = [
                "blastn",
                "-query",
                str(query_path),
                "-subject",
                str(target_path),
                *args,
                "-outfmt",
                "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore",
                "-out",
                str(output_path),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
            if result.returncode != 0:
                raise RuntimeError((result.stderr or result.stdout or shlex.join(command)).strip())
            return parse_alignment_text(output_path.read_text(encoding="utf-8", errors="replace"), "blast6")

        args = strip_arg_values(args, {"-o"})
        command = ["minimap2", *args, str(target_path), str(query_path)]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=180)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or shlex.join(command)).strip())
        return parse_alignment_text(result.stdout, "paf")


def strip_arg_values(args: List[str], names: set[str]) -> List[str]:
    cleaned: List[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in names:
            skip_next = True
            continue
        if any(arg.startswith(f"{name}=") for name in names):
            continue
        cleaned.append(arg)
    return cleaned


def exact_query_hits(graph: GfaGraph, query_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    records = parse_fasta(query_path.read_text(encoding="utf-8", errors="replace"))
    if not records:
        raise ValueError(f"No FASTA records found in {query_path}")
    missing_sequences = [segment.id for segment in graph.segments.values() if segment.sequence is None]
    if missing_sequences:
        raise ValueError("Exact query fallback requires graph sequences; the GFA has '*' sequences or missing sequence fields")
    hits_by_query: Dict[str, List[Dict[str, Any]]] = {}
    for query_id, query_sequence in records:
        query = query_sequence.upper()
        query_rc = reverse_complement(query)
        hits: List[Dict[str, Any]] = []
        for segment in graph.segments.values():
            target = (segment.sequence or "").upper()
            hit = exact_hit(query_id, query, target, segment.id, strand="+")
            if hit is None and query_rc != query:
                hit = exact_hit(query_id, query_rc, target, segment.id, strand="-")
            if hit is not None:
                hits.append(hit)
        hits_by_query[query_id] = hits
    return hits_by_query


def exact_hit(query_id: str, query: str, target: str, target_id: str, *, strand: str) -> Optional[Dict[str, Any]]:
    if not query or not target:
        return None
    position = target.find(query)
    if position >= 0:
        return {
            "qseqid": query_id,
            "sseqid": target_id,
            "pident": 100.0,
            "length": len(query),
            "mismatch": 0,
            "gapopen": 0,
            "qstart": 1,
            "qend": len(query),
            "sstart": position + 1,
            "send": position + len(query),
            "evalue": 0.0,
            "bitscore": len(query) * 2,
            "strand": strand,
        }
    position = query.find(target)
    if position >= 0:
        return {
            "qseqid": query_id,
            "sseqid": target_id,
            "pident": 100.0,
            "length": len(target),
            "mismatch": 0,
            "gapopen": 0,
            "qstart": position + 1,
            "qend": position + len(target),
            "sstart": 1,
            "send": len(target),
            "evalue": 0.0,
            "bitscore": len(target) * 2,
            "strand": strand,
        }
    return None


def parse_fasta(text: str) -> List[Tuple[str, str]]:
    records: List[Tuple[str, str]] = []
    current_name: Optional[str] = None
    current_chunks: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current_name is not None:
                records.append((current_name, "".join(current_chunks)))
            current_name = line[1:].split()[0] or f"query_{len(records) + 1}"
            current_chunks = []
        elif current_name is not None:
            current_chunks.append(line)
    if current_name is not None:
        records.append((current_name, "".join(current_chunks)))
    return records


def reverse_complement(sequence: str) -> str:
    return sequence.translate(DNA_COMPLEMENT)[::-1]


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    raise SystemExit(main())
