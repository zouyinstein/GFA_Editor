# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

from __future__ import annotations

import html
import math
import random
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

from .gfa_core import GfaGraph, best_blast_hit
from .graph_ops import graph_is_circular_subgraph, valid_graph_links


Color = Tuple[int, int, int]

BACKGROUND = (251, 252, 248)
INK = (31, 37, 33)
MUTED = (112, 122, 108)
EDGE = (155, 167, 151)
UNHIT = (219, 225, 212)
PALETTE: List[Color] = [
    (47, 111, 175),
    (190, 80, 60),
    (71, 143, 105),
    (151, 91, 168),
    (207, 139, 53),
    (56, 154, 166),
    (177, 76, 123),
    (102, 122, 52),
]


@dataclass
class RenderNode:
    id: str
    label: str
    x: float
    y: float
    angle: float
    length_px: float
    width_px: float
    color: Color
    points: Optional[List[Tuple[float, float]]] = None


@dataclass
class RenderEdge:
    source: str
    target: str
    label: str
    points: List[Tuple[float, float]]
    color: Color
    width_px: float
    self_loop: bool = False


@dataclass
class RenderScene:
    width: int
    height: int
    nodes: List[RenderNode]
    edges: List[RenderEdge]
    title: str


def render_graph(
    graph: GfaGraph,
    output_path: Path,
    *,
    width: int = 1400,
    height: int = 1000,
    layout: str = "bandage",
    colour: str = "depth",
    show_labels: bool = True,
    title: str = "GFA graph",
) -> None:
    render_width = int(width)
    render_height = int(height)
    if not is_bandage_layout(layout) or (render_width > 0 and render_height > 0):
        render_width = max(320, render_width)
        render_height = max(240, render_height)
    scene = build_scene(
        graph,
        width=render_width,
        height=render_height,
        layout=layout,
        colour=colour,
        show_labels=show_labels,
        title=title,
    )
    suffix = output_path.suffix.lower()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".svg":
        output_path.write_text(scene_to_svg(scene), encoding="utf-8")
        return
    if suffix == ".pdf":
        output_path.write_bytes(scene_to_pdf(scene))
        return
    if suffix in {".png", ""}:
        output_path.write_bytes(scene_to_png(scene))
        return
    raise ValueError("Image output extension must be .svg, .png, or .pdf")


def build_scene(
    graph: GfaGraph,
    *,
    width: int,
    height: int,
    layout: str,
    colour: str,
    show_labels: bool,
    title: str,
) -> RenderScene:
    if is_bandage_layout(layout):
        return build_bandage_scene(
            graph,
            width=width,
            height=height,
            colour=colour,
            show_labels=show_labels,
            title=title,
        )

    positions = layout_positions(graph, width, height, layout)
    max_length = max((segment.length for segment in graph.segments.values()), default=1)
    max_support = max((link.support or 0 for link in graph.links), default=1) or 1
    node_order = list(graph.segments)

    nodes: List[RenderNode] = []
    for node_id, segment in graph.segments.items():
        x, y = positions[node_id]
        normalized = math.log10(max(segment.length, 1)) / math.log10(max(max_length, 10))
        label = node_id if show_labels else ""
        nodes.append(
            RenderNode(
                id=node_id,
                label=label,
                x=x,
                y=y,
                angle=node_angle(node_id, positions, graph),
                length_px=44 + normalized * 132,
                width_px=9 + normalized * 9,
                color=node_colour(graph, node_id, colour),
            )
        )

    edges: List[RenderEdge] = []
    for index, link in enumerate(valid_graph_links(graph)):
        if link.source not in positions or link.target not in positions:
            continue
        color = edge_colour(link, colour)
        width_px = 1.8 + min(6.0, 4.5 * ((link.support or 0) / max_support))
        label = "" if not show_labels else (str(int(link.support)) if link.support else "")
        points = edge_points(link.source, link.target, positions, index)
        edges.append(
            RenderEdge(
                source=link.source,
                target=link.target,
                label=label,
                points=points,
                color=color,
                width_px=width_px,
                self_loop=link.source == link.target,
            )
        )

    nodes.sort(key=lambda item: node_order.index(item.id) if item.id in node_order else 0)
    return RenderScene(width=width, height=height, nodes=nodes, edges=edges, title=title)


def layout_positions(graph: GfaGraph, width: int, height: int, layout: str) -> Dict[str, Tuple[float, float]]:
    node_ids = list(graph.segments)
    if not node_ids:
        return {}
    normalized = layout.lower()
    if normalized == "auto":
        normalized = "circle" if graph_is_circular_subgraph(graph) or len(graph.segments) <= 3 else "spring"
    if normalized in {"circle", "circular"}:
        return circle_positions(node_ids, width, height)
    if normalized in {"grid", "tile"}:
        return grid_positions(node_ids, width, height)
    if normalized not in {"spring", "force"}:
        raise ValueError("Layout must be auto, spring, circle, or grid")
    return spring_positions(graph, width, height)


def is_bandage_layout(layout: str) -> bool:
    normalized = (layout or "bandage").strip().lower().replace("-", "_")
    return normalized in {"auto", "band", "bandage", "bandage_native"}


def build_bandage_scene(
    graph: GfaGraph,
    *,
    width: int,
    height: int,
    colour: str,
    show_labels: bool,
    title: str,
) -> RenderScene:
    states = bandage_endpoint_layout(graph)
    raw_nodes: List[RenderNode] = []
    raw_edges: List[RenderEdge] = []
    contig_width = 18.0
    links = valid_graph_links(graph)
    max_support = max((link.support or 0 for link in links), default=1) or 1

    for node_id, segment in graph.segments.items():
        points = states.get(node_id)
        if not points:
            continue
        center = average_point(points)
        start = points[0]
        end = points[-1]
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        length_px = polyline_length(points)
        raw_nodes.append(
            RenderNode(
                id=node_id,
                label=node_id if show_labels else "",
                x=center[0],
                y=center[1],
                angle=angle,
                length_px=length_px,
                width_px=contig_width,
                color=node_colour(graph, node_id, colour),
                points=points,
            )
        )

    for index, link in enumerate(links):
        source_points = states.get(link.source)
        target_points = states.get(link.target)
        if not source_points or not target_points:
            continue
        source = bandage_endpoint(source_points, link.source_orient, "source")
        target = bandage_endpoint(target_points, link.target_orient, "target")
        points = bandage_link_points(source, target, link.id, index)
        color = edge_colour(link, colour)
        width_px = max(2.3, (1.5 + min(5.0, 5.0 * ((link.support or 0) / max_support))) * 0.78)
        label = "" if not show_labels else (str(int(link.support)) if link.support else "")
        raw_edges.append(
            RenderEdge(
                source=link.source,
                target=link.target,
                label=label,
                points=points,
                color=color,
                width_px=width_px,
            )
        )

    if raw_nodes or raw_edges:
        if width <= 0 or height <= 0:
            width, height = frame_bandage_scene_auto(raw_nodes, raw_edges)
        else:
            fit_bandage_scene(raw_nodes, raw_edges, width, height)

    return RenderScene(width=width, height=height, nodes=raw_nodes, edges=raw_edges, title=title)


def bandage_endpoint_layout(graph: GfaGraph) -> Dict[str, List[Tuple[float, float]]]:
    node_ids = list(graph.segments)
    if not node_ids:
        return {}
    glyph_lengths = bandage_glyph_lengths(graph)
    cycle = longest_simple_cycle(graph)
    centered = cycle_seed_centers(graph, cycle, glyph_lengths) if len(cycle) >= 4 else {}
    if not centered:
        centers = spring_positions(graph, 1200, 1000)
        centered = {
            node_id: (point[0] - 600.0, point[1] - 500.0)
            for node_id, point in centers.items()
        }
    endpoint_points: Dict[str, Dict[str, List[float]]] = {}
    for index, node_id in enumerate(node_ids):
        center = centered.get(node_id) or fallback_bandage_center(index, len(node_ids))
        angle = estimate_bandage_angle(graph, node_id, centered, index)
        half = glyph_lengths.get(node_id, 80.0) / 2.0
        direction = (math.cos(angle), math.sin(angle))
        endpoint_points[f"{node_id}:-"] = [center[0] - direction[0] * half, center[1] - direction[1] * half]
        endpoint_points[f"{node_id}:+"] = [center[0] + direction[0] * half, center[1] + direction[1] * half]
    anchors = {key: [point[0], point[1]] for key, point in endpoint_points.items()}

    springs: List[Tuple[str, str, float, float]] = []
    for node_id in node_ids:
        springs.append((f"{node_id}:-", f"{node_id}:+", glyph_lengths.get(node_id, 80.0), 0.16))
    for link in valid_graph_links(graph):
        source_key = f"{link.source}:{gfa_endpoint_side(link.source_orient, 'source')}"
        target_key = f"{link.target}:{gfa_endpoint_side(link.target_orient, 'target')}"
        if source_key in endpoint_points and target_key in endpoint_points:
            springs.append((source_key, target_key, 34.0, 0.34))

    keys = list(endpoint_points)
    for step in range(520):
        alpha = 1.0 - step / 520.0
        cooling = 0.25 + alpha * 0.75
        displacements = {key: [0.0, 0.0] for key in keys}
        for source_key, target_key, desired, strength in springs:
            source = endpoint_points[source_key]
            target = endpoint_points[target_key]
            dx = target[0] - source[0]
            dy = target[1] - source[1]
            distance = max(math.hypot(dx, dy), 0.001)
            force = (distance - desired) * strength * cooling
            fx = dx / distance * force
            fy = dy / distance * force
            displacements[source_key][0] += fx
            displacements[source_key][1] += fy
            displacements[target_key][0] -= fx
            displacements[target_key][1] -= fy

        for first_index, first_key in enumerate(keys):
            first = endpoint_points[first_key]
            first_node = first_key.rsplit(":", 1)[0]
            for second_key in keys[first_index + 1 :]:
                second_node = second_key.rsplit(":", 1)[0]
                if first_node == second_node:
                    continue
                second = endpoint_points[second_key]
                dx = first[0] - second[0]
                dy = first[1] - second[1]
                distance = math.hypot(dx, dy)
                if distance < 0.001:
                    angle = math.tau * hash_number(f"{first_key}:{second_key}:repel")
                    dx = math.cos(angle)
                    dy = math.sin(angle)
                    distance = 1.0
                charge_distance = 270.0
                collision_distance = 34.0
                if distance >= charge_distance and distance >= collision_distance:
                    continue
                force = 0.0
                if distance < collision_distance:
                    force += (collision_distance - distance) * 0.34
                if distance < charge_distance:
                    force += (4200.0 / max(distance * distance, 36.0)) * ((1.0 - distance / charge_distance) ** 1.55)
                force *= cooling
                fx = dx / distance * force
                fy = dy / distance * force
                displacements[first_key][0] += fx
                displacements[first_key][1] += fy
                displacements[second_key][0] -= fx
                displacements[second_key][1] -= fy

        for key, point in endpoint_points.items():
            dx, dy = displacements[key]
            anchor = anchors[key]
            dx += (anchor[0] - point[0]) * 0.025
            dy += (anchor[1] - point[1]) * 0.025
            point[0] += clamp(dx - point[0] * 0.00035, -22.0, 22.0)
            point[1] += clamp(dy - point[1] * 0.00035, -22.0, 22.0)

        if step % 12 == 0:
            constrain_bandage_internal_lengths(endpoint_points, glyph_lengths, strength=0.42)

    constrain_bandage_internal_lengths(endpoint_points, glyph_lengths, strength=0.75)
    states: Dict[str, List[Tuple[float, float]]] = {}
    for node_id in node_ids:
        start = tuple(endpoint_points[f"{node_id}:-"])
        end = tuple(endpoint_points[f"{node_id}:+"])
        bend = deterministic_signed_value(node_id) * 1.9
        states[node_id] = create_native_polyline_points(start, end, bend, node_id, glyph_lengths.get(node_id, 80.0))
    return states


def longest_simple_cycle(graph: GfaGraph) -> List[str]:
    node_ids = list(graph.segments)
    if len(node_ids) > 42:
        return []
    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
    for link in valid_graph_links(graph):
        if link.source in adjacency and link.target in adjacency:
            adjacency[link.source].append(link.target)
            adjacency[link.target].append(link.source)
    cycles: Set[Tuple[str, ...]] = set()
    max_cycles = 8000

    def canonical(path: List[str]) -> Tuple[str, ...]:
        variants: List[Tuple[str, ...]] = []
        for sequence in (path, list(reversed(path))):
            for index in range(len(sequence)):
                variants.append(tuple(sequence[index:] + sequence[:index]))
        return min(variants)

    def dfs(start: str, current: str, path: List[str], used: Set[str]) -> None:
        if len(cycles) >= max_cycles:
            return
        for neighbor in adjacency.get(current, []):
            if neighbor == start and len(path) >= 3:
                cycles.add(canonical(path.copy()))
            elif neighbor not in used and len(path) < len(node_ids):
                used.add(neighbor)
                path.append(neighbor)
                dfs(start, neighbor, path, used)
                path.pop()
                used.remove(neighbor)

    for node_id in node_ids:
        dfs(node_id, node_id, [node_id], {node_id})
        if len(cycles) >= max_cycles:
            break
    if not cycles:
        return []
    selected = list(
        max(
            cycles,
            key=lambda cycle: (
                len(cycle),
                sum(graph.segments[node_id].length for node_id in cycle if node_id in graph.segments),
            ),
        )
    )
    if len(selected) > 2:
        return [selected[0], *reversed(selected[1:])]
    return selected


def cycle_seed_centers(
    graph: GfaGraph,
    cycle: List[str],
    glyph_lengths: Dict[str, float],
) -> Dict[str, Tuple[float, float]]:
    if len(cycle) < 4:
        return {}
    weights = [math.sqrt(max(glyph_lengths.get(node_id, 40.0), 34.0)) for node_id in cycle]
    total = sum(weights) or 1.0
    radius_x = max(280.0, min(380.0, total / math.tau * 0.82))
    radius_y = max(430.0, min(560.0, total / math.tau * 1.25))
    start_angle = -0.42
    centers: Dict[str, Tuple[float, float]] = {}
    cursor = 0.0
    for node_id, weight in zip(cycle, weights):
        theta = start_angle + math.tau * (cursor + weight / 2.0) / total
        centers[node_id] = (math.cos(theta) * radius_x, math.sin(theta) * radius_y)
        cursor += weight

    cycle_set = set(cycle)
    unresolved = [node_id for node_id in graph.segments if node_id not in cycle_set]
    for _ in range(len(unresolved) + 2):
        changed = False
        for node_id in list(unresolved):
            neighbors = [
                other
                for other in graph_neighbors(graph, node_id)
                if other in centers
            ]
            if not neighbors:
                continue
            average = (
                sum(centers[other][0] for other in neighbors) / len(neighbors),
                sum(centers[other][1] for other in neighbors) / len(neighbors),
            )
            inward = 0.58 if len(neighbors) >= 2 else 0.82
            angle = math.tau * hash_number(f"{node_id}:branch-offset")
            jitter = 34.0 + 22.0 * hash_number(f"{node_id}:branch-radius")
            centers[node_id] = (
                average[0] * inward + math.cos(angle) * jitter,
                average[1] * inward + math.sin(angle) * jitter,
            )
            unresolved.remove(node_id)
            changed = True
        if not changed:
            break
    for index, node_id in enumerate(unresolved):
        centers[node_id] = fallback_bandage_center(index, len(graph.segments))
    return centers


def graph_neighbors(graph: GfaGraph, node_id: str) -> List[str]:
    neighbors: List[str] = []
    for link in valid_graph_links(graph):
        if link.source == node_id:
            neighbors.append(link.target)
        elif link.target == node_id:
            neighbors.append(link.source)
    return neighbors


def bandage_glyph_lengths(graph: GfaGraph) -> Dict[str, float]:
    node_count = max(len(graph.segments), 1)
    max_glyph = 560.0 if node_count <= 70 else 420.0 if node_count <= 180 else 300.0
    min_glyph = 30.0 if node_count <= 180 else 22.0
    max_length = max((segment.length for segment in graph.segments.values()), default=1) or 1
    pixels_per_bp = max_glyph / max_length
    return {
        node_id: max(min_glyph, segment.length * pixels_per_bp)
        for node_id, segment in graph.segments.items()
    }


def fallback_bandage_center(index: int, count: int) -> Tuple[float, float]:
    radius = 120.0 + math.sqrt(max(count, 1)) * 46.0
    angle = math.tau * index / max(count, 1)
    lane = 1.0 + (index % 4) * 0.18
    return math.cos(angle) * radius * lane, math.sin(angle) * radius * lane


def estimate_bandage_angle(
    graph: GfaGraph,
    node_id: str,
    centers: Dict[str, Tuple[float, float]],
    index: int,
) -> float:
    center = centers.get(node_id) or fallback_bandage_center(index, max(len(graph.segments), 1))
    vx = 0.0
    vy = 0.0
    for link in valid_graph_links(graph):
        attached_as_source = link.source == node_id
        attached_as_target = link.target == node_id
        if not attached_as_source and not attached_as_target:
            continue
        other_id = link.target if attached_as_source else link.source
        other = centers.get(other_id)
        if other is None:
            continue
        dx = other[0] - center[0]
        dy = other[1] - center[1]
        distance = max(math.hypot(dx, dy), 1.0)
        side = gfa_endpoint_side(link.source_orient if attached_as_source else link.target_orient, "source" if attached_as_source else "target")
        sign = -1.0 if side == "-" else 1.0
        vx += dx / distance * sign
        vy += dy / distance * sign
    if math.hypot(vx, vy) > 0.08:
        return math.atan2(vy, vx)
    return math.tau * hash_number(f"{node_id}:{index}")


def gfa_endpoint_side(orient: str, role: str) -> str:
    if role == "target":
        return "+" if orient == "-" else "-"
    return "-" if orient == "-" else "+"


def bandage_endpoint(points: List[Tuple[float, float]], orient: str, role: str) -> Tuple[float, float]:
    return points[0] if gfa_endpoint_side(orient, role) == "-" else points[-1]


def constrain_bandage_internal_lengths(
    endpoint_points: Dict[str, List[float]],
    glyph_lengths: Dict[str, float],
    *,
    strength: float,
) -> None:
    for node_id, desired in glyph_lengths.items():
        start = endpoint_points.get(f"{node_id}:-")
        end = endpoint_points.get(f"{node_id}:+")
        if not start or not end:
            continue
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        distance = max(math.hypot(dx, dy), 0.001)
        correction = (distance - desired) * 0.5 * strength
        cx = dx / distance * correction
        cy = dy / distance * correction
        start[0] += cx
        start[1] += cy
        end[0] -= cx
        end[1] -= cy


def create_native_polyline_points(
    start: Tuple[float, float],
    end: Tuple[float, float],
    bend: float,
    seed: str,
    target_length: float,
) -> List[Tuple[float, float]]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    chord = max(math.hypot(dx, dy), 1.0)
    direction = (dx / chord, dy / chord)
    normal = (-direction[1], direction[0])
    segment_count = max(2, min(28, math.ceil(max(target_length, 1.0) / 44.0)))
    desired_segment = max(target_length / segment_count, 1.0)
    chord_step = chord / segment_count
    target_angle = math.radians(148.0)
    target_offset = chord_step / max(math.tan(target_angle / 2.0), 0.001)
    folded_amplitude = math.sqrt(max(desired_segment * desired_segment - chord_step * chord_step, 0.0)) * 0.18
    kink_direction = 1.0 if hash_number(f"{seed}:kink-side") > 0.5 else -1.0
    kink_amplitude = max(4.0, min(34.0, max(target_offset, min(target_length * 0.08, folded_amplitude * 0.35))))
    phase = math.pi if hash_number(f"{seed}:kink-phase") > 0.5 else 0.0
    points: List[Tuple[float, float]] = []
    for index in range(segment_count + 1):
        t = index / segment_count
        envelope = math.sin(math.pi * t)
        arc_offset = bend * 0.16 * envelope
        native_arc = 0.0 if index in {0, segment_count} else kink_direction * kink_amplitude * envelope
        small_facet = math.sin(math.tau * t + phase) * kink_amplitude * 0.04 * envelope
        offset = arc_offset + native_arc + small_facet
        points.append(
            (
                start[0] + direction[0] * chord * t + normal[0] * offset,
                start[1] + direction[1] * chord * t + normal[1] * offset,
            )
        )
    return points


def bandage_link_points(
    source: Tuple[float, float],
    target: Tuple[float, float],
    edge_id: str,
    index: int,
) -> List[Tuple[float, float]]:
    dx = target[0] - source[0]
    dy = target[1] - source[1]
    distance = max(math.hypot(dx, dy), 1.0)
    normal = (-dy / distance, dx / distance)
    bend_seed = hash_number(f"{edge_id}:bend")
    bend = min(18.0, max(4.0, distance * 0.16 + bend_seed * 9.0))
    bend *= 1.0 if hash_number(f"{edge_id}:side") > 0.5 else -1.0
    bend += ((index % 3) - 1) * 10.0
    control = (
        (source[0] + target[0]) / 2.0 + normal[0] * bend,
        (source[1] + target[1]) / 2.0 + normal[1] * bend,
    )
    return quadratic_points(source, control, target, steps=18)


def fit_bandage_scene(nodes: List[RenderNode], edges: List[RenderEdge], width: int, height: int) -> None:
    points: List[Tuple[float, float]] = []
    for node in nodes:
        points.extend(node_points(node))
    for edge in edges:
        points.extend(edge.points)
    if not points:
        return
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    padding = 70.0
    scale = min(
        (width - padding * 2) / max(max_x - min_x, 1.0),
        (height - padding * 2) / max(max_y - min_y, 1.0),
    )
    scale = max(0.08, min(3.2, scale))
    offset_x = width / 2.0 - ((min_x + max_x) / 2.0) * scale
    offset_y = height / 2.0 - ((min_y + max_y) / 2.0) * scale

    def transform(point: Tuple[float, float]) -> Tuple[float, float]:
        return point[0] * scale + offset_x, point[1] * scale + offset_y

    for node in nodes:
        if node.points:
            node.points = [transform(point) for point in node.points]
            node.x, node.y = average_point(node.points)
            start = node.points[0]
            end = node.points[-1]
            node.angle = math.atan2(end[1] - start[1], end[0] - start[0])
            node.length_px = polyline_length(node.points)
        else:
            node.x, node.y = transform((node.x, node.y))
            node.length_px *= scale
        node.width_px = max(6.0, min(56.0, node.width_px))
    for edge in edges:
        edge.points = [transform(point) for point in edge.points]


def frame_bandage_scene_auto(nodes: List[RenderNode], edges: List[RenderEdge]) -> Tuple[int, int]:
    points: List[Tuple[float, float]] = []
    for node in nodes:
        points.extend(node_points(node))
    for edge in edges:
        points.extend(edge.points)
    if not points:
        return 320, 240
    margin = 34.0
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max(320, math.ceil(max_x - min_x + margin * 2))
    height = max(240, math.ceil(max_y - min_y + margin * 2))
    offset_x = margin - min_x
    offset_y = margin - min_y

    def transform(point: Tuple[float, float]) -> Tuple[float, float]:
        return point[0] + offset_x, point[1] + offset_y

    for node in nodes:
        if node.points:
            node.points = [transform(point) for point in node.points]
            node.x, node.y = average_point(node.points)
            start = node.points[0]
            end = node.points[-1]
            node.angle = math.atan2(end[1] - start[1], end[0] - start[0])
            node.length_px = polyline_length(node.points)
        else:
            node.x, node.y = transform((node.x, node.y))
    for edge in edges:
        edge.points = [transform(point) for point in edge.points]
    return width, height


def average_point(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    if not points:
        return 0.0, 0.0
    return sum(point[0] for point in points) / len(points), sum(point[1] for point in points) / len(points)


def polyline_length(points: List[Tuple[float, float]]) -> float:
    return sum(math.hypot(end[0] - start[0], end[1] - start[1]) for start, end in zip(points, points[1:]))


def hash_number(value: str) -> float:
    result = 2166136261
    for char in value:
        result ^= ord(char)
        result = (result * 16777619) & 0xFFFFFFFF
    return (result % 10000) / 10000.0


def deterministic_signed_value(value: str) -> float:
    return (hash_number(value) - 0.5) * 2.0


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def circle_positions(node_ids: List[str], width: int, height: int) -> Dict[str, Tuple[float, float]]:
    cx = width / 2
    cy = height / 2
    radius_factor = 0.28 if len(node_ids) <= 3 else 0.37
    radius = max(60.0, min(width, height) * radius_factor)
    if len(node_ids) == 1:
        return {node_ids[0]: (cx, cy)}
    positions = {}
    for index, node_id in enumerate(node_ids):
        angle = -math.pi / 2 + 2 * math.pi * index / len(node_ids)
        positions[node_id] = (cx + radius * math.cos(angle), cy + radius * math.sin(angle))
    return positions


def grid_positions(node_ids: List[str], width: int, height: int) -> Dict[str, Tuple[float, float]]:
    columns = max(1, math.ceil(math.sqrt(len(node_ids) * width / max(height, 1))))
    rows = math.ceil(len(node_ids) / columns)
    margin_x = width * 0.08
    margin_y = height * 0.1
    usable_w = max(1.0, width - margin_x * 2)
    usable_h = max(1.0, height - margin_y * 2)
    positions = {}
    for index, node_id in enumerate(node_ids):
        row, column = divmod(index, columns)
        x = margin_x + (column + 0.5) * usable_w / columns
        y = margin_y + (row + 0.5) * usable_h / rows
        positions[node_id] = (x, y)
    return positions


def spring_positions(graph: GfaGraph, width: int, height: int) -> Dict[str, Tuple[float, float]]:
    node_ids = list(graph.segments)
    positions = {
        node_id: (math.cos(index * 2.399963), math.sin(index * 2.399963))
        for index, node_id in enumerate(node_ids)
    }
    links = [
        (link.source, link.target)
        for link in valid_graph_links(graph)
        if link.source in positions and link.target in positions and link.source != link.target
    ]
    n = max(len(node_ids), 1)
    k = math.sqrt(4.0 / n)
    temperature = 1.4
    iterations = 240 if n <= 120 else 120
    rng = random.Random(42)

    for _ in range(iterations):
        disp = {node_id: [0.0, 0.0] for node_id in node_ids}
        for i, first in enumerate(node_ids):
            x1, y1 = positions[first]
            for second in node_ids[i + 1 :]:
                x2, y2 = positions[second]
                dx = x1 - x2
                dy = y1 - y2
                distance = math.hypot(dx, dy) or 0.001
                force = (k * k) / distance
                ux = dx / distance
                uy = dy / distance
                disp[first][0] += ux * force
                disp[first][1] += uy * force
                disp[second][0] -= ux * force
                disp[second][1] -= uy * force
        for source, target in links:
            x1, y1 = positions[source]
            x2, y2 = positions[target]
            dx = x1 - x2
            dy = y1 - y2
            distance = math.hypot(dx, dy) or 0.001
            force = (distance * distance) / k
            ux = dx / distance
            uy = dy / distance
            disp[source][0] -= ux * force
            disp[source][1] -= uy * force
            disp[target][0] += ux * force
            disp[target][1] += uy * force
        for node_id in node_ids:
            dx, dy = disp[node_id]
            distance = math.hypot(dx, dy)
            if distance == 0:
                dx = rng.uniform(-0.01, 0.01)
                dy = rng.uniform(-0.01, 0.01)
                distance = math.hypot(dx, dy)
            step = min(distance, temperature) / distance
            x, y = positions[node_id]
            positions[node_id] = (x + dx * step, y + dy * step)
        temperature *= 0.975

    xs = [point[0] for point in positions.values()]
    ys = [point[1] for point in positions.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    pad_x = width * 0.12
    pad_y = height * 0.14
    scale_x = (width - 2 * pad_x) / max(max_x - min_x, 0.001)
    scale_y = (height - 2 * pad_y) / max(max_y - min_y, 0.001)
    scale = min(scale_x, scale_y)
    return {
        node_id: (
            pad_x + (point[0] - min_x) * scale + ((width - 2 * pad_x) - (max_x - min_x) * scale) / 2,
            pad_y + (point[1] - min_y) * scale + ((height - 2 * pad_y) - (max_y - min_y) * scale) / 2,
        )
        for node_id, point in positions.items()
    }


def node_angle(node_id: str, positions: Dict[str, Tuple[float, float]], graph: GfaGraph) -> float:
    if len(positions) <= 3:
        return 0.0
    neighbors = []
    x, y = positions[node_id]
    for link in valid_graph_links(graph):
        other = None
        if link.source == node_id and link.target in positions:
            other = link.target
        elif link.target == node_id and link.source in positions:
            other = link.source
        if other is None or other == node_id:
            continue
        ox, oy = positions[other]
        neighbors.append((ox - x, oy - y))
    if neighbors:
        dx = sum(item[0] for item in neighbors)
        dy = sum(item[1] for item in neighbors)
        if math.hypot(dx, dy) > 0.001:
            return math.atan2(dy, dx)
    cx = sum(point[0] for point in positions.values()) / len(positions)
    cy = sum(point[1] for point in positions.values()) / len(positions)
    return math.atan2(y - cy, x - cx) + math.pi / 2


def edge_points(
    source: str,
    target: str,
    positions: Dict[str, Tuple[float, float]],
    index: int,
) -> List[Tuple[float, float]]:
    sx, sy = positions[source]
    tx, ty = positions[target]
    if source == target:
        radius = 42.0
        return [
            (sx, sy - radius),
            (sx + radius * 0.8, sy - radius * 1.3),
            (sx + radius * 1.15, sy),
            (sx + radius * 0.8, sy + radius * 1.3),
            (sx, sy + radius),
        ]
    mx = (sx + tx) / 2
    my = (sy + ty) / 2
    dx = tx - sx
    dy = ty - sy
    dist = math.hypot(dx, dy) or 1
    bend = ((index % 5) - 2) * 7
    cx = mx - dy / dist * bend
    cy = my + dx / dist * bend
    return quadratic_points((sx, sy), (cx, cy), (tx, ty), steps=18)


def quadratic_points(
    start: Tuple[float, float],
    control: Tuple[float, float],
    end: Tuple[float, float],
    *,
    steps: int,
) -> List[Tuple[float, float]]:
    points = []
    for index in range(steps + 1):
        t = index / steps
        a = (1 - t) * (1 - t)
        b = 2 * (1 - t) * t
        c = t * t
        points.append(
            (
                a * start[0] + b * control[0] + c * end[0],
                a * start[1] + b * control[1] + c * end[1],
            )
        )
    return points


def node_colour(graph: GfaGraph, node_id: str, mode: str) -> Color:
    segment = graph.segments[node_id]
    custom = segment.tags.get("CL", {}).get("raw")
    if custom:
        parsed = parse_hex_color(str(custom))
        if parsed:
            return parsed
    normalized = normalize_colour(mode)
    if normalized == "blastsolid":
        hit = best_blast_hit(segment.blast_hits)
        return query_colour(str(hit.get("qseqid") or "")) if hit else UNHIT
    if normalized == "random":
        return hash_colour(node_id)
    if normalized == "degree":
        degree = sum(1 for link in graph.links if link.source == node_id or link.target == node_id)
        return gradient(min(degree / 6, 1), (219, 225, 212), (184, 86, 61))
    if normalized == "solid":
        return (89, 146, 137)
    max_depth = max((segment.depth or 0 for segment in graph.segments.values()), default=1) or 1
    return depth_colour((segment.depth or 0) / max_depth)


def edge_colour(link, mode: str) -> Color:
    custom = link.tags.get("CL", {}).get("raw")
    if custom:
        parsed = parse_hex_color(str(custom))
        if parsed:
            return parsed
    if normalize_colour(mode) == "blastsolid" and link.blast_hits:
        hit = best_blast_hit(link.blast_hits)
        return query_colour(str(hit.get("qseqid") or "")) if hit else EDGE
    return EDGE


def normalize_colour(mode: str) -> str:
    normalized = (mode or "depth").strip().lower().replace("_", "").replace("-", "")
    aliases = {
        "blast": "blastsolid",
        "alignment": "blastsolid",
        "alignments": "blastsolid",
        "readpath": "blastsolid",
        "depth": "depth",
        "dp": "depth",
        "random": "random",
        "degree": "degree",
        "solid": "solid",
    }
    return aliases.get(normalized, normalized)


def depth_colour(value: float) -> Color:
    clamped = max(0.0, min(value, 1.0))
    if clamped < 0.55:
        return gradient(clamped / 0.55, (228, 235, 225), (89, 146, 137))
    return gradient((clamped - 0.55) / 0.45, (89, 146, 137), (184, 86, 61))


def gradient(value: float, low: Color, high: Color) -> Color:
    t = max(0.0, min(value, 1.0))
    return tuple(round(low[i] + (high[i] - low[i]) * t) for i in range(3))  # type: ignore[return-value]


def hash_colour(value: str) -> Color:
    seed = 0
    for char in value:
        seed = (seed * 131 + ord(char)) & 0xFFFFFFFF
    rng = random.Random(seed)
    hue = rng.random()
    return hsl_to_rgb(hue, 0.48, 0.58)


def query_colour(query_id: str) -> Color:
    if not query_id:
        return PALETTE[0]
    seed = sum((index + 1) * ord(char) for index, char in enumerate(query_id))
    return PALETTE[seed % len(PALETTE)]


def hsl_to_rgb(h: float, s: float, l: float) -> Color:
    def hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        value = round(l * 255)
        return (value, value, value)
    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    return (
        round(hue_to_rgb(p, q, h + 1 / 3) * 255),
        round(hue_to_rgb(p, q, h) * 255),
        round(hue_to_rgb(p, q, h - 1 / 3) * 255),
    )


def parse_hex_color(value: str) -> Optional[Color]:
    cleaned = value.strip()
    if len(cleaned) != 7 or not cleaned.startswith("#"):
        return None
    try:
        return (int(cleaned[1:3], 16), int(cleaned[3:5], 16), int(cleaned[5:7], 16))
    except ValueError:
        return None


def css(color: Color) -> str:
    return f"rgb({color[0]}, {color[1]}, {color[2]})"


def scene_to_svg(scene: RenderScene) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="{scene.width}" height="{scene.height}" viewBox="0 0 {scene.width} {scene.height}">',
        f"<title>{html.escape(scene.title)}</title>",
        '<rect x="0" y="0" width="100%" height="100%" fill="#fbfcf8"/>',
    ]
    lines.append('<g fill="none" stroke-linecap="round" stroke-linejoin="round">')
    for edge in scene.edges:
        if len(edge.points) < 2:
            continue
        path = points_to_svg_path(edge.points)
        lines.append(
            f'<path d="{path}" stroke="{css(edge.color)}" stroke-width="{edge.width_px:.2f}" opacity="0.78"/>'
        )
        arrow = arrow_polygon(edge.points, max(7.0, edge.width_px + 4))
        if arrow:
            lines.append(f'<polygon points="{svg_points(arrow)}" fill="{css(edge.color)}" opacity="0.82"/>')
        if edge.label:
            x, y = edge.points[len(edge.points) // 2]
            lines.append(svg_text(edge.label, x, y - 8, 9, MUTED))
    lines.append("</g>")

    for node in scene.nodes:
        points = node_points(node)
        x1, y1 = points[0]
        x2, y2 = points[-1]
        node_path = points_to_svg_path(points)
        lines.append(
            f'<path d="{node_path}" fill="none" stroke="{css(node.color)}" '
            f'stroke-width="{node.width_px:.2f}" stroke-linecap="butt" stroke-linejoin="round"/>'
        )
        lines.append(
            f'<circle cx="{x1:.2f}" cy="{y1:.2f}" r="3.90" fill="#1f2521" opacity="0.85"/>'
        )
        lines.append(
            f'<circle cx="{x2:.2f}" cy="{y2:.2f}" r="3.90" fill="#1f2521" opacity="0.85"/>'
        )
        if node.label:
            lines.append(svg_text("-", x1, y1 + 0.2, 7, (255, 255, 255), weight="700"))
            lines.append(svg_text("+", x2, y2 + 0.2, 7, (255, 255, 255), weight="700"))
            lines.append(svg_text(node.label, node.x, node.y + node.width_px + 13, 10, INK))
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def svg_text(text: str, x: float, y: float, size: int, color: Color, *, weight: str = "400") -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{css(color)}" font-size="{size}" '
        f'font-weight="{weight}" font-family="Inter,Arial,sans-serif" text-anchor="middle" dominant-baseline="central">'
        f"{html.escape(text)}</text>"
    )


def points_to_svg_path(points: List[Tuple[float, float]]) -> str:
    if len(points) == 3:
        return f"M {points[0][0]:.2f} {points[0][1]:.2f} Q {points[1][0]:.2f} {points[1][1]:.2f} {points[2][0]:.2f} {points[2][1]:.2f}"
    return " ".join(
        [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
        + [f"L {x:.2f} {y:.2f}" for x, y in points[1:]]
    )


def svg_points(points: List[Tuple[float, float]]) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in points)


def node_axis(node: RenderNode) -> Tuple[float, float, float, float]:
    dx = math.cos(node.angle) * node.length_px / 2
    dy = math.sin(node.angle) * node.length_px / 2
    return node.x - dx, node.y - dy, node.x + dx, node.y + dy


def node_points(node: RenderNode) -> List[Tuple[float, float]]:
    if node.points and len(node.points) >= 2:
        return node.points
    x1, y1, x2, y2 = node_axis(node)
    return [(x1, y1), (x2, y2)]


def arrow_polygon(points: List[Tuple[float, float]], size: float) -> List[Tuple[float, float]]:
    if len(points) < 2:
        return []
    x2, y2 = points[-1]
    x1, y1 = points[-2]
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.001:
        return []
    ux, uy = dx / length, dy / length
    px, py = -uy, ux
    base_x = x2 - ux * size
    base_y = y2 - uy * size
    return [
        (x2, y2),
        (base_x + px * size * 0.45, base_y + py * size * 0.45),
        (base_x - px * size * 0.45, base_y - py * size * 0.45),
    ]


def scene_to_png(scene: RenderScene) -> bytes:
    canvas = RasterCanvas(scene.width, scene.height, BACKGROUND)
    for edge in scene.edges:
        canvas.polyline(edge.points, edge.color, max(1, int(round(edge.width_px))))
        arrow = arrow_polygon(edge.points, max(7.0, edge.width_px + 4))
        if arrow:
            canvas.polygon(arrow, edge.color)
        if edge.label:
            x, y = edge.points[len(edge.points) // 2]
            canvas.text(edge.label, int(x), int(y - 13), MUTED, scale=1, centered=True)
    for node in scene.nodes:
        points = node_points(node)
        x1, y1 = points[0]
        x2, y2 = points[-1]
        canvas.polyline(points, node.color, max(3, int(round(node.width_px))))
        endpoint_radius = 4
        canvas.circle(x1, y1, endpoint_radius, INK)
        canvas.circle(x2, y2, endpoint_radius, INK)
        if node.label:
            canvas.text("-", int(x1), int(y1 - 3), (255, 255, 255), scale=1, centered=True)
            canvas.text("+", int(x2), int(y2 - 3), (255, 255, 255), scale=1, centered=True)
            canvas.text(node.label, int(node.x), int(node.y + node.width_px + 14), INK, scale=1, centered=True)
    return canvas.to_png()


class RasterCanvas:
    def __init__(self, width: int, height: int, background: Color) -> None:
        self.width = width
        self.height = height
        self.pixels = bytearray(background * (width * height))

    def set_pixel(self, x: int, y: int, color: Color) -> None:
        if x < 0 or y < 0 or x >= self.width or y >= self.height:
            return
        offset = (y * self.width + x) * 3
        self.pixels[offset : offset + 3] = bytes(color)

    def circle(self, cx: float, cy: float, radius: int, color: Color) -> None:
        left = math.floor(cx - radius)
        right = math.ceil(cx + radius)
        top = math.floor(cy - radius)
        bottom = math.ceil(cy + radius)
        rr = radius * radius
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                if (x - cx) * (x - cx) + (y - cy) * (y - cy) <= rr:
                    self.set_pixel(x, y, color)

    def line(self, x1: float, y1: float, x2: float, y2: float, color: Color, width: int) -> None:
        steps = max(1, int(math.hypot(x2 - x1, y2 - y1)))
        radius = max(1, width // 2)
        for index in range(steps + 1):
            t = index / steps
            self.circle(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, radius, color)

    def polyline(self, points: List[Tuple[float, float]], color: Color, width: int) -> None:
        for start, end in zip(points, points[1:]):
            self.line(start[0], start[1], end[0], end[1], color, width)

    def polygon(self, points: List[Tuple[float, float]], color: Color) -> None:
        if len(points) < 3:
            return
        min_y = math.floor(min(y for _, y in points))
        max_y = math.ceil(max(y for _, y in points))
        for y in range(min_y, max_y + 1):
            intersections = []
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
                if y1 == y2:
                    continue
                if (y >= min(y1, y2)) and (y < max(y1, y2)):
                    intersections.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
            intersections.sort()
            for x_start, x_end in zip(intersections[0::2], intersections[1::2]):
                for x in range(math.floor(x_start), math.ceil(x_end) + 1):
                    self.set_pixel(x, y, color)

    def text(self, text: str, x: int, y: int, color: Color, *, scale: int = 1, centered: bool = False) -> None:
        rendered = text.upper()
        width = text_width(rendered, scale)
        cursor_x = x - width // 2 if centered else x
        for char in rendered:
            glyph = FONT.get(char, FONT.get("?"))
            if glyph is None:
                cursor_x += 4 * scale
                continue
            for row_index, row in enumerate(glyph):
                for column_index, pixel in enumerate(row):
                    if pixel != "1":
                        continue
                    for yy in range(scale):
                        for xx in range(scale):
                            self.set_pixel(cursor_x + column_index * scale + xx, y + row_index * scale + yy, color)
            cursor_x += (len(glyph[0]) + 1) * scale

    def to_png(self) -> bytes:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.pixels[y * stride : (y + 1) * stride])
        return make_png(self.width, self.height, bytes(raw))


def make_png(width: int, height: int, raw_scanlines: bytes) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
        )

    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(raw_scanlines, 9)),
            chunk(b"IEND", b""),
        ]
    )


def text_width(text: str, scale: int) -> int:
    total = 0
    for char in text:
        glyph = FONT.get(char, FONT.get("?"))
        total += ((len(glyph[0]) if glyph else 3) + 1) * scale
    return max(0, total - scale)


def scene_to_pdf(scene: RenderScene) -> bytes:
    commands = ["0 J 1 j"]
    commands.append(f"{pdf_color(BACKGROUND)} rg 0 0 {scene.width} {scene.height} re f")
    for edge in scene.edges:
        commands.append(pdf_stroke(edge.color, edge.width_px))
        commands.extend(pdf_polyline(edge.points, scene.height))
        arrow = arrow_polygon(edge.points, max(7.0, edge.width_px + 4))
        if arrow:
            commands.append(pdf_fill_polygon(arrow, edge.color, scene.height))
        if edge.label:
            x, y = edge.points[len(edge.points) // 2]
            commands.append(pdf_text(edge.label, x, y - 10, 8, MUTED, scene.height))
    for node in scene.nodes:
        points = node_points(node)
        x1, y1 = points[0]
        x2, y2 = points[-1]
        commands.append(pdf_stroke(node.color, node.width_px))
        commands.extend(pdf_polyline(points, scene.height))
        endpoint_radius = 3.9
        commands.append(pdf_circle(x1, y1, endpoint_radius, INK, scene.height))
        commands.append(pdf_circle(x2, y2, endpoint_radius, INK, scene.height))
        if node.label:
            commands.append(pdf_text("-", x1, y1 + 1.8, 7, (255, 255, 255), scene.height))
            commands.append(pdf_text("+", x2, y2 + 1.8, 7, (255, 255, 255), scene.height))
            commands.append(pdf_text(node.label, node.x, node.y + node.width_px + 13, 8, INK, scene.height))
    return encode_pdf(scene.width, scene.height, "\n".join(commands) + "\n")


def pdf_color(color: Color) -> str:
    return f"{color[0] / 255:.4f} {color[1] / 255:.4f} {color[2] / 255:.4f}"


def pdf_stroke(color: Color, width: float) -> str:
    return f"{pdf_color(color)} RG {width:.2f} w"


def pdf_polyline(points: List[Tuple[float, float]], height: int) -> List[str]:
    if len(points) < 2:
        return []
    bits = [f"{points[0][0]:.2f} {height - points[0][1]:.2f} m"]
    bits.extend(f"{x:.2f} {height - y:.2f} l" for x, y in points[1:])
    bits.append("S")
    return [" ".join(bits)]


def pdf_fill_polygon(points: List[Tuple[float, float]], color: Color, height: int) -> str:
    bits = [f"{pdf_color(color)} rg {points[0][0]:.2f} {height - points[0][1]:.2f} m"]
    bits.extend(f"{x:.2f} {height - y:.2f} l" for x, y in points[1:])
    bits.append("h f")
    return " ".join(bits)


def pdf_circle(cx: float, cy: float, radius: float, color: Color, height: int) -> str:
    k = 0.5522847498
    y = height - cy
    r = radius
    return (
        f"{pdf_color(color)} rg "
        f"{cx + r:.2f} {y:.2f} m "
        f"{cx + r:.2f} {y + k * r:.2f} {cx + k * r:.2f} {y + r:.2f} {cx:.2f} {y + r:.2f} c "
        f"{cx - k * r:.2f} {y + r:.2f} {cx - r:.2f} {y + k * r:.2f} {cx - r:.2f} {y:.2f} c "
        f"{cx - r:.2f} {y - k * r:.2f} {cx - k * r:.2f} {y - r:.2f} {cx:.2f} {y - r:.2f} c "
        f"{cx + k * r:.2f} {y - r:.2f} {cx + r:.2f} {y - k * r:.2f} {cx + r:.2f} {y:.2f} c f"
    )


def pdf_text(text: str, x: float, y: float, size: int, color: Color, height: int) -> str:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    approx_width = len(text) * size * 0.52
    return (
        f"{pdf_color(color)} rg BT /F1 {size} Tf "
        f"{x - approx_width / 2:.2f} {height - y:.2f} Td ({escaped}) Tj ET"
    )


def encode_pdf(width: int, height: int, content: str) -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ).encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content.encode('utf-8'))} >>\nstream\n{content}endstream".encode("utf-8"),
    ]
    chunks = [b"%PDF-1.4\n%\xff\xff\xff\xff\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n")
    xref_offset = sum(len(chunk) for chunk in chunks)
    xref = [f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii")]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    ).encode("ascii")
    return b"".join([*chunks, *xref, trailer])


FONT: Dict[str, List[str]] = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10011", "10001", "10001", "01111"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["00111", "01000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00010", "11100"],
    "_": ["00000", "00000", "00000", "00000", "00000", "00000", "11111"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    "+": ["00000", "00100", "00100", "11111", "00100", "00100", "00000"],
    "/": ["00001", "00001", "00010", "00100", "01000", "10000", "10000"],
    "?": ["01110", "10001", "00001", "00010", "00100", "00000", "00100"],
}
