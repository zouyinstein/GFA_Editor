# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

from __future__ import annotations

import asyncio
import copy
import contextvars
from dataclasses import dataclass, field
from datetime import datetime, timezone
import io
import json
import os
import posixpath
import re
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
    parse_gfa_lines,
    parse_alignment_text,
    parse_blast_outfmt6,
    parse_gfa_text,
    repeat_resolve_node,
    rotate_circular_node,
    update_edge,
    update_node,
)
from .graph_ops import (
    AutoRepeatCandidate,
    build_auto_repeat_resolution_candidates,
    graph_topology_signature,
)
from .edit_history import (
    apply_edit_history,
    build_history_document,
    history_step_from_event,
    infer_edit_history,
)


ROOT_DIR = Path(os.environ.get("GFA_EDITOR_ROOT", Path(__file__).resolve().parents[1])).resolve()
FRONTEND_DIR = Path(os.environ.get("GFA_EDITOR_FRONTEND_DIR", ROOT_DIR / "frontend")).resolve()
SERVER_DATA_DIR = Path(os.environ.get("GFA_EDITOR_DATA_DIR", ROOT_DIR / "server_data")).expanduser()
INSTANCE_ID = os.environ.get("GFA_EDITOR_INSTANCE_ID", "")
SERVER_FILE_EXTENSIONS = {".gfa", ".txt"}
SEQUENCE_LOAD_TIMEOUT_SECONDS = max(1.0, float(os.environ.get("GFA_EDITOR_SEQUENCE_LOAD_TIMEOUT_SECONDS", "10")))
DEFAULT_SPLIT_MAX_ELEMENTS = max(1, int(os.environ.get("GFA_EDITOR_SPLIT_MAX_ELEMENTS", "100000")))
DEFAULT_SPLIT_NODE_THRESHOLD = max(1, int(os.environ.get("GFA_EDITOR_SPLIT_NODE_THRESHOLD", "200")))
DEFAULT_REMAINING_CHUNK_SIZE = max(1, int(os.environ.get("GFA_EDITOR_REMAINING_CHUNK_SIZE", "50")))
AUTO_REPEAT_MAX_STATES = max(1, int(os.environ.get("GFA_EDITOR_AUTO_REPEAT_MAX_STATES", "5000")))
AUTO_REPEAT_MAX_CANDIDATES = max(1, int(os.environ.get("GFA_EDITOR_AUTO_REPEAT_MAX_CANDIDATES", "100")))
CACHE_DIR_NAME = ".gfa-editor-cache"
SESSION_HEADER = "X-GFA-Session-Id"
SESSION_COOKIE = "gfa_editor_session"
DEFAULT_SESSION_ID = "default"
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
MAX_SESSIONS = max(1, int(os.environ.get("GFA_EDITOR_MAX_SESSIONS", "64")))
SESSION_TTL_SECONDS = max(60, int(os.environ.get("GFA_EDITOR_SESSION_TTL_SECONDS", "86400")))
current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "gfa_editor_session_id",
    default=DEFAULT_SESSION_ID,
)


def coerce_positive_int(value: Any, default: int) -> int:
    try:
        return max(1, int(value or default))
    except (TypeError, ValueError):
        return max(1, int(default))


@dataclass
class SessionState:
    graph: Optional[GfaGraph]
    edit_steps: List[Dict[str, Any]]
    source_name: Optional[str]
    sequence_source_path: Optional[str]
    sequence_source_name: Optional[str]
    sequence_source_size: Optional[int]
    light_mode: bool
    light_mode_reason: Optional[str]
    sequence_load_seconds: Optional[float]
    alignment_hits_by_query: Dict[str, List[Dict[str, Any]]]
    alignment_format: Optional[str]
    alignment_target_role: str
    alignment_source_name: Optional[str]
    alignment_selected_read_id: Optional[str]
    alignment_last_command: Optional[str]
    alignment_last_stderr: Optional[str]
    active_operation_state_index: Optional[int]


@dataclass
class LoadedGfa:
    graph: GfaGraph
    cache_path: Path
    light_mode: bool
    light_mode_reason: Optional[str]
    sequence_load_seconds: float
    source_size: int


@dataclass
class SplitComponentState:
    id: str
    label: str
    export_suffix: str
    original_node_ids: List[str]
    is_remaining_group: bool
    graph: GfaGraph
    edit_steps: List[Dict[str, Any]] = field(default_factory=list)
    log: List[Dict[str, Any]] = field(default_factory=list)
    undo_stack: List[SessionState] = field(default_factory=list)
    redo_stack: List[SessionState] = field(default_factory=list)
    operation_states: List[SessionState] = field(default_factory=list)
    active_operation_state_index: Optional[int] = None
    history_trace_snapshots: List[Tuple[GfaGraph, List[Dict[str, Any]]]] = field(default_factory=list)
    history_trace: List[Dict[str, Any]] = field(default_factory=list)
    history_trace_index: Optional[int] = None
    version: int = 1


class EditorSession:
    def __init__(self) -> None:
        self.lock = threading.RLock()
        self.graph: Optional[GfaGraph] = None
        self.undo_stack: List[SessionState] = []
        self.redo_stack: List[SessionState] = []
        self.log: List[Dict[str, Any]] = []
        self.edit_steps: List[Dict[str, Any]] = []
        self.operation_states: List[SessionState] = []
        self.active_operation_state_index: Optional[int] = None
        self.history_trace_snapshots: List[Tuple[GfaGraph, List[Dict[str, Any]]]] = []
        self.history_trace: List[Dict[str, Any]] = []
        self.history_trace_index: Optional[int] = None
        self.version = 0
        self.source_name: Optional[str] = None
        self.sequence_source_path: Optional[str] = None
        self.sequence_source_name: Optional[str] = None
        self.sequence_source_size: Optional[int] = None
        self.light_mode = False
        self.light_mode_reason: Optional[str] = None
        self.sequence_load_seconds: Optional[float] = None
        self.alignment_hits_by_query: Dict[str, List[Dict[str, Any]]] = {}
        self.alignment_format: Optional[str] = None
        self.alignment_target_role: str = "subject"
        self.alignment_source_name: Optional[str] = None
        self.alignment_selected_read_id: Optional[str] = None
        self.alignment_last_command: Optional[str] = None
        self.alignment_last_stderr: Optional[str] = None
        self.split_enabled = False
        self.split_max_elements_per_view = DEFAULT_SPLIT_MAX_ELEMENTS
        self.split_remaining_chunk_size = DEFAULT_REMAINING_CHUNK_SIZE
        self.split_original_file_name: Optional[str] = None
        self.split_original_node_count = 0
        self.split_original_link_count = 0
        self.split_components: List[SplitComponentState] = []
        self.selected_component_id: Optional[str] = None
        self.split_warning: Optional[str] = None
        self.auto_repeat_candidates: List[AutoRepeatCandidate] = []
        self.auto_repeat_base_signature: Optional[str] = None
        self.auto_repeat_warning: Optional[str] = None

    def has_graph(self) -> GfaGraph:
        if self.graph is None:
            raise HTTPException(status_code=409, detail="No GFA graph is loaded")
        return self.graph

    def sequence_cache_ready(self) -> bool:
        return bool(self.sequence_source_path and Path(self.sequence_source_path).is_file())

    def graph_with_sequences(self) -> GfaGraph:
        graph = self.has_graph()
        if not graph.dropped_sequences:
            return graph
        if not self.sequence_source_path:
            raise HTTPException(
                status_code=409,
                detail="This graph is in light mode but no original GFA cache is available for sequence rebuild.",
            )
        source_path = Path(self.sequence_source_path)
        if not source_path.is_file():
            raise HTTPException(
                status_code=409,
                detail=f"Original GFA cache is missing: {source_path}",
            )
        try:
            with source_path.open("rb") as handle:
                rebuilt = parse_gfa_lines(handle, keep_sequences=True)
            if self.split_enabled:
                component = self._selected_split_component()
                if component is not None:
                    rebuilt = subgraph_from_node_ids(rebuilt, component.original_node_ids)
            if self.edit_steps:
                apply_edit_history(rebuilt, {"steps": self.edit_steps})
            deduplicate_links(rebuilt)
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f"Could not rebuild sequences from original GFA: {exc}") from exc
        return rebuilt

    def load(
        self,
        graph: GfaGraph,
        source_name: str,
        *,
        sequence_source_path: Optional[Path] = None,
        sequence_source_size: Optional[int] = None,
        light_mode: bool = False,
        light_mode_reason: Optional[str] = None,
        sequence_load_seconds: Optional[float] = None,
        auto_split: bool = True,
        max_elements_per_view: int = DEFAULT_SPLIT_MAX_ELEMENTS,
        remaining_chunk_size: int = DEFAULT_REMAINING_CHUNK_SIZE,
    ) -> Dict[str, Any]:
        previous_state = self._capture_state() if self.graph is not None else None
        deduplicate_links(graph)
        max_elements_per_view = coerce_positive_int(max_elements_per_view, DEFAULT_SPLIT_MAX_ELEMENTS)
        remaining_chunk_size = coerce_positive_int(remaining_chunk_size, DEFAULT_REMAINING_CHUNK_SIZE)
        split_components, split_warning = build_split_components(
            graph,
            max_elements_per_view=max_elements_per_view,
            remaining_chunk_size=remaining_chunk_size,
            auto_split=auto_split,
        )
        self._clear_split()
        if split_components:
            self.split_enabled = True
            self.split_max_elements_per_view = max_elements_per_view
            self.split_remaining_chunk_size = remaining_chunk_size
            self.split_original_file_name = source_name
            self.split_original_node_count = len(graph.segments)
            self.split_original_link_count = len(graph.links)
            self.split_components = split_components
            self.selected_component_id = split_components[0].id
            self.split_warning = split_warning
            self.graph = split_components[0].graph.clone()
            split_components[0].graph = self.graph.clone()
        else:
            self.graph = graph
        self.undo_stack = [] if split_components else ([previous_state] if previous_state is not None else [])
        self.redo_stack.clear()
        self.edit_steps.clear()
        self._clear_history_trace()
        self._clear_auto_repeat_candidates()
        self._clear_alignment()
        self.log.clear()
        self.operation_states.clear()
        self.active_operation_state_index = None
        self.version = 1
        self.source_name = source_name
        self.sequence_source_path = str(sequence_source_path) if sequence_source_path is not None else None
        self.sequence_source_name = source_name if sequence_source_path is not None else None
        self.sequence_source_size = sequence_source_size
        self.light_mode = light_mode
        self.light_mode_reason = light_mode_reason
        self.sequence_load_seconds = sequence_load_seconds
        self._append_log("upload", {"source_name": source_name, "edit_step_count": 0})
        self._save_selected_split_component()
        return self.snapshot()

    def snapshot(self, include_sequences: bool = False) -> Dict[str, Any]:
        graph = self.has_graph()
        if deduplicate_links(graph):
            self._refresh_alignment()
        self._save_selected_split_component()
        payload = graph.to_client(include_sequences=include_sequences)
        payload["session"] = {
            "version": self.version,
            "source_name": self.source_name,
            "can_undo": bool(self.undo_stack),
            "can_redo": bool(self.redo_stack),
            "edit_step_count": len(self.edit_steps),
            "history": self.log[-30:],
            "operation_state_index": self.active_operation_state_index,
            "history_trace": self.history_trace,
            "history_trace_index": self.history_trace_index,
            "alignment": self.alignment_summary(),
            "light_mode": self.light_mode,
            "light_mode_reason": self.light_mode_reason,
            "sequence_cache_ready": self.sequence_cache_ready(),
            "sequence_source_name": self.sequence_source_name,
            "sequence_source_size": self.sequence_source_size,
            "sequence_load_seconds": self.sequence_load_seconds,
            "split": self._split_summary(),
            "autoRepeatResolution": self._auto_repeat_summary(),
        }
        return payload

    def select_split_component(self, component_id: str) -> Dict[str, Any]:
        self.has_graph()
        if not self.split_enabled:
            raise HTTPException(status_code=409, detail="No large-graph split is active")
        component = self._split_component_by_id(component_id)
        if component is None:
            raise HTTPException(status_code=404, detail=f"Subgraph not found: {component_id}")
        if component.id == self.selected_component_id:
            return self.snapshot()
        self._clear_auto_repeat_candidates()
        self._save_selected_split_component()
        self.selected_component_id = component.id
        self._restore_split_component(component)
        return self.snapshot()

    def default_export_filename(self, extension: str, *, selection: bool = False) -> str:
        source_name = strip_server_prefix(self.split_original_file_name or self.source_name or "edited")
        stem = Path(source_name).stem or "edited"
        component = self._selected_split_component()
        if component is not None:
            kind = "selected-links" if selection else "edited"
            return f"{stem}.{component.export_suffix}.{kind}.{extension}"
        kind = "selected-links" if selection else "edited"
        return f"{stem}.{kind}.{extension}"

    def default_server_export_path(self, extension: str) -> str:
        filename = self.default_export_filename(extension)
        component = self._selected_split_component()
        if component is None:
            return filename
        source_name = strip_server_prefix(self.split_original_file_name or self.source_name or "edited")
        stem = Path(source_name).stem or "edited"
        return f"{stem}.components/{filename}"

    def _clear_split(self) -> None:
        self.split_enabled = False
        self.split_max_elements_per_view = DEFAULT_SPLIT_MAX_ELEMENTS
        self.split_remaining_chunk_size = DEFAULT_REMAINING_CHUNK_SIZE
        self.split_original_file_name = None
        self.split_original_node_count = 0
        self.split_original_link_count = 0
        self.split_components.clear()
        self.selected_component_id = None
        self.split_warning = None

    def _split_component_by_id(self, component_id: Optional[str]) -> Optional[SplitComponentState]:
        if not component_id:
            return None
        return next((component for component in self.split_components if component.id == component_id), None)

    def _selected_split_component(self) -> Optional[SplitComponentState]:
        if not self.split_enabled:
            return None
        return self._split_component_by_id(self.selected_component_id)

    def _clone_state_list(self, states: List[SessionState]) -> List[SessionState]:
        return [self._clone_state(state) for state in states]

    def _clone_history_trace_snapshots(self) -> List[Tuple[GfaGraph, List[Dict[str, Any]]]]:
        return [
            (graph.clone(), copy.deepcopy(steps))
            for graph, steps in self.history_trace_snapshots
        ]

    def _save_selected_split_component(self) -> None:
        component = self._selected_split_component()
        if component is None or self.graph is None:
            return
        component.graph = self.graph.clone()
        component.edit_steps = copy.deepcopy(self.edit_steps)
        component.log = copy.deepcopy(self.log)
        component.undo_stack = self._clone_state_list(self.undo_stack)
        component.redo_stack = self._clone_state_list(self.redo_stack)
        component.operation_states = self._clone_state_list(self.operation_states)
        component.active_operation_state_index = self.active_operation_state_index
        component.history_trace_snapshots = self._clone_history_trace_snapshots()
        component.history_trace = copy.deepcopy(self.history_trace)
        component.history_trace_index = self.history_trace_index
        component.version = self.version

    def _restore_split_component(self, component: SplitComponentState) -> None:
        self.graph = component.graph.clone()
        self.edit_steps = copy.deepcopy(component.edit_steps)
        self.log = copy.deepcopy(component.log)
        self.undo_stack = self._clone_state_list(component.undo_stack)
        self.redo_stack = self._clone_state_list(component.redo_stack)
        self.operation_states = self._clone_state_list(component.operation_states)
        self.active_operation_state_index = component.active_operation_state_index
        self.history_trace_snapshots = [
            (graph.clone(), copy.deepcopy(steps))
            for graph, steps in component.history_trace_snapshots
        ]
        self.history_trace = copy.deepcopy(component.history_trace)
        self.history_trace_index = component.history_trace_index
        self.version = component.version
        self._refresh_alignment()

    @staticmethod
    def _component_summary(component: SplitComponentState) -> Dict[str, Any]:
        node_count = len(component.graph.segments)
        link_count = len(component.graph.links)
        return {
            "id": component.id,
            "label": component.label,
            "nodeCount": node_count,
            "linkCount": link_count,
            "elementCount": node_count + link_count,
            "isRemainingGroup": component.is_remaining_group,
            "exportSuffix": component.export_suffix,
        }

    def _split_summary(self) -> Dict[str, Any]:
        if not self.split_enabled:
            return {"splitEnabled": False}
        return {
            "originalFileName": self.split_original_file_name,
            "originalNodeCount": self.split_original_node_count,
            "originalLinkCount": self.split_original_link_count,
            "originalElementCount": self.split_original_node_count + self.split_original_link_count,
            "splitEnabled": True,
            "maxElementsPerView": self.split_max_elements_per_view,
            "remainingChunkSize": self.split_remaining_chunk_size,
            "nodeSplitThreshold": DEFAULT_SPLIT_NODE_THRESHOLD,
            "selectedComponentId": self.selected_component_id,
            "warning": self.split_warning,
            "components": [
                self._component_summary(component)
                for component in self.split_components
            ],
        }

    def _auto_repeat_summary(self) -> Dict[str, Any]:
        return {
            "candidateCount": len(self.auto_repeat_candidates),
            "warning": self.auto_repeat_warning,
            "candidates": [
                candidate.summary()
                for candidate in self.auto_repeat_candidates
            ],
        }

    def _clear_auto_repeat_candidates(self) -> None:
        self.auto_repeat_candidates.clear()
        self.auto_repeat_base_signature = None
        self.auto_repeat_warning = None

    def mutate(self, action: str, details: Dict[str, Any], callback) -> Dict[str, Any]:
        graph = self.has_graph()
        self.undo_stack.append(self._capture_state())
        self.redo_stack.clear()
        try:
            result = callback(graph)
            removed_duplicate_edges = deduplicate_links(graph)
        except Exception:
            self._restore_state(self.undo_stack.pop())
            raise
        event_details = {**details, **(result or {})}
        if removed_duplicate_edges:
            event_details["removed_duplicate_edges"] = removed_duplicate_edges
        self._record_edit_step(action, event_details, result or {})
        event_details["edit_step_count"] = len(self.edit_steps)
        self.version += 1
        self._refresh_alignment()
        self._clear_auto_repeat_candidates()
        self._append_log(action, event_details)
        return self.snapshot()

    def apply_alignment(
        self,
        hits_by_query: Dict[str, List[Dict[str, Any]]],
        *,
        format: str,
        target_role: str,
        source_name: str,
        command: Optional[str] = None,
        stderr: Optional[str] = None,
    ) -> Dict[str, Any]:
        self.has_graph()
        self.undo_stack.append(self._capture_state())
        self.redo_stack.clear()
        try:
            self.alignment_hits_by_query = copy.deepcopy(hits_by_query)
            self.alignment_format = format
            self.alignment_target_role = target_role
            self.alignment_source_name = source_name
            self.alignment_selected_read_id = None
            self.alignment_last_command = command
            self.alignment_last_stderr = stderr
            result = self._refresh_alignment()
        except Exception:
            self._restore_state(self.undo_stack.pop())
            raise
        self.version += 1
        self._append_log(
            "alignment",
            {
                "source_name": source_name,
                "format": format,
                "target_role": target_role,
                "read_count": len(self.alignment_hits_by_query),
                "edit_step_count": len(self.edit_steps),
                **result,
            },
        )
        self._clear_auto_repeat_candidates()
        return self.snapshot()

    def select_alignment_read(self, read_id: Optional[str]) -> Dict[str, Any]:
        self.has_graph()
        normalized = None if read_id in {None, "", "__all__"} else str(read_id)
        if normalized and normalized not in self.alignment_hits_by_query:
            raise HTTPException(status_code=404, detail=f"Alignment read not found: {normalized}")
        self.alignment_selected_read_id = normalized
        self._refresh_alignment()
        self.version += 1
        return self.snapshot()

    def generate_auto_repeat_resolution_candidates(self) -> Dict[str, Any]:
        graph = self.has_graph()
        self._clear_auto_repeat_candidates()
        self.auto_repeat_base_signature = graph_topology_signature(graph)
        candidates, warning = build_auto_repeat_resolution_candidates(
            graph,
            max_states=AUTO_REPEAT_MAX_STATES,
            max_candidates=AUTO_REPEAT_MAX_CANDIDATES,
        )
        self.auto_repeat_candidates = candidates
        self.auto_repeat_warning = warning
        return self.snapshot()

    def apply_auto_repeat_resolution_candidate(self, candidate_id: str) -> Dict[str, Any]:
        graph = self.has_graph()
        candidate = next(
            (item for item in self.auto_repeat_candidates if item.id == candidate_id),
            None,
        )
        if candidate is None:
            raise HTTPException(status_code=404, detail=f"Auto repeat resolution candidate not found: {candidate_id}")
        if self.auto_repeat_base_signature != graph_topology_signature(graph):
            self._clear_auto_repeat_candidates()
            raise HTTPException(status_code=409, detail="The graph changed after candidates were generated. Generate candidates again.")

        initial_state = self._capture_state()
        original_undo_stack = self._clone_state_list(self.undo_stack)
        original_redo_stack = self._clone_state_list(self.redo_stack)
        original_log = copy.deepcopy(self.log)
        original_operation_states = self._clone_state_list(self.operation_states)
        original_active_operation_state_index = self.active_operation_state_index
        original_history_trace_snapshots = self._clone_history_trace_snapshots()
        original_history_trace = copy.deepcopy(self.history_trace)
        original_history_trace_index = self.history_trace_index

        self.redo_stack.clear()
        try:
            for step in candidate.steps:
                self.undo_stack.append(self._capture_state())
                result = apply_edit_history(graph, {"steps": [step]})
                applied_step = result["applied_steps"][0]
                removed_duplicate_edges = deduplicate_links(graph)
                self.edit_steps.append(copy.deepcopy(applied_step))
                event_details = {
                    **copy.deepcopy(applied_step.get("params") or {}),
                    **copy.deepcopy(applied_step.get("result") or {}),
                    "auto_candidate_id": candidate.id,
                }
                if removed_duplicate_edges:
                    event_details["removed_duplicate_edges"] = removed_duplicate_edges
                event_details["edit_step_count"] = len(self.edit_steps)
                self.version += 1
                self._refresh_alignment()
                self._append_log(str(applied_step.get("action")), event_details)
            if graph_topology_signature(graph) != candidate.signature:
                raise ValueError("Applied auto repeat resolution did not reproduce the selected candidate")
        except Exception:
            self._restore_state(initial_state)
            self.undo_stack = original_undo_stack
            self.redo_stack = original_redo_stack
            self.log = original_log
            self.operation_states = original_operation_states
            self.active_operation_state_index = original_active_operation_state_index
            self.history_trace_snapshots = original_history_trace_snapshots
            self.history_trace = original_history_trace
            self.history_trace_index = original_history_trace_index
            raise

        self.version += 1
        self._clear_auto_repeat_candidates()
        self._append_log(
            "auto_repeat_resolution",
            {
                "candidate_id": candidate.id,
                "step_count": len(candidate.steps),
                "resolved_node_count": len(candidate.order),
                "order": [
                    f"{item.get('nodeId')}:{item.get('strategy')}"
                    for item in candidate.order
                ],
                "circular": candidate.circular,
                "merged_order_count": candidate.merged_order_count,
                "edit_step_count": len(self.edit_steps),
            },
        )
        return self.snapshot()

    def alignment_summary(self) -> Dict[str, Any]:
        read_ids = sorted(self.alignment_hits_by_query)
        return {
            "read_ids": read_ids,
            "read_count": len(read_ids),
            "selected_read_id": self.alignment_selected_read_id or "__all__",
            "format": self.alignment_format,
            "target_role": self.alignment_target_role,
            "source_name": self.alignment_source_name,
            "last_command": self.alignment_last_command,
            "last_stderr": self.alignment_last_stderr,
        }

    def _refresh_alignment(self) -> Dict[str, Any]:
        if not self.graph:
            return {}
        if not self.alignment_hits_by_query:
            self._clear_graph_alignment_hits()
            return {}
        if self.alignment_selected_read_id:
            hits = {
                self.alignment_selected_read_id: copy.deepcopy(
                    self.alignment_hits_by_query[self.alignment_selected_read_id]
                )
            }
        else:
            hits = copy.deepcopy(self.alignment_hits_by_query)
        return attach_blast_hits(
            self.graph,
            hits,
            target_role=self.alignment_target_role,
            source_name=self.alignment_source_name or "alignment",
        )

    def _clear_alignment(self) -> None:
        self.alignment_hits_by_query.clear()
        self.alignment_format = None
        self.alignment_target_role = "subject"
        self.alignment_source_name = None
        self.alignment_selected_read_id = None
        self.alignment_last_command = None
        self.alignment_last_stderr = None
        self._clear_graph_alignment_hits()

    def _clear_graph_alignment_hits(self) -> None:
        if not self.graph:
            return
        for segment in self.graph.segments.values():
            segment.blast_hits.clear()
        for link in self.graph.links:
            link.blast_hits.clear()

    def undo(self) -> Dict[str, Any]:
        self._undo_once(record_log=False)
        return self.snapshot()

    def redo(self) -> Dict[str, Any]:
        self._redo_once(record_log=False)
        return self.snapshot()

    def jump_edit_step(self, target_step_count: int) -> Dict[str, Any]:
        self.has_graph()
        if target_step_count < 0:
            raise HTTPException(status_code=400, detail="Target step must be non-negative")
        reachable_steps = {
            len(self.edit_steps),
            *[len(state.edit_steps) for state in self.undo_stack],
            *[len(state.edit_steps) for state in self.redo_stack],
        }
        if target_step_count not in reachable_steps:
            raise HTTPException(status_code=409, detail="Target step is not reachable from undo/redo history")
        while len(self.edit_steps) > target_step_count:
            self._undo_once(record_log=False)
        while len(self.edit_steps) < target_step_count:
            self._redo_once(record_log=False)
        return self.snapshot()

    def _undo_once(self, record_log: bool) -> None:
        self.has_graph()
        if not self.undo_stack:
            raise HTTPException(status_code=409, detail="Nothing to undo")
        self.redo_stack.append(self._capture_state())
        self._restore_state(self.undo_stack.pop())
        self.version += 1
        self._clear_auto_repeat_candidates()
        if record_log:
            self._append_log("undo", {"edit_step_count": len(self.edit_steps)})

    def _redo_once(self, record_log: bool) -> None:
        self.has_graph()
        if not self.redo_stack:
            raise HTTPException(status_code=409, detail="Nothing to redo")
        self.undo_stack.append(self._capture_state())
        self._restore_state(self.redo_stack.pop())
        self.version += 1
        self._clear_auto_repeat_candidates()
        if record_log:
            self._append_log("redo", {"edit_step_count": len(self.edit_steps)})

    def export_history(self) -> Dict[str, Any]:
        self.has_graph()
        return build_history_document(self.edit_steps, source_name=self.source_name)

    def apply_history_document(self, history_document: Dict[str, Any], history_name: str) -> Dict[str, Any]:
        graph = self.has_graph()
        steps = history_document.get("steps")
        if not isinstance(steps, list):
            raise ValueError("History file must contain a steps list")

        self.undo_stack.append(self._capture_state())
        self.redo_stack.clear()
        cumulative_steps = copy.deepcopy(self.edit_steps)
        trace_snapshots: List[Tuple[GfaGraph, List[Dict[str, Any]]]] = [
            (graph.clone(), copy.deepcopy(cumulative_steps))
        ]
        trace_entries: List[Dict[str, Any]] = [
            {
                **self._event(
                    "history_start",
                    {"history_name": history_name, "step": 0, "step_count": len(steps)},
                ),
                "trace_index": 0,
            }
        ]

        try:
            for index, step in enumerate(steps, start=1):
                result = apply_edit_history(graph, {"steps": [step]})
                applied_step = result["applied_steps"][0]
                cumulative_steps.append(copy.deepcopy(applied_step))
                trace_snapshots.append((graph.clone(), copy.deepcopy(cumulative_steps)))
                trace_entries.append(
                    {
                        **self._event(
                            str(applied_step.get("action")),
                            {
                                "step": index,
                                "params": copy.deepcopy(applied_step.get("params") or {}),
                                "result": copy.deepcopy(applied_step.get("result") or {}),
                            },
                        ),
                        "trace_index": index,
                    }
                )
        except Exception:
            self._restore_state(self.undo_stack.pop())
            self._clear_history_trace()
            self._clear_auto_repeat_candidates()
            raise

        self.edit_steps = cumulative_steps
        self.history_trace_snapshots = trace_snapshots
        self.history_trace = trace_entries
        self.history_trace_index = len(trace_entries) - 1
        self.version += 1
        self._clear_auto_repeat_candidates()
        self._append_log("import_history", {"history_name": history_name, "step_count": len(steps)})
        self.log.extend(trace_entries[1:])
        return self.snapshot()

    def restore_history_trace_step(self, trace_index: int) -> Dict[str, Any]:
        self.has_graph()
        if not self.history_trace_snapshots:
            raise HTTPException(status_code=409, detail="No imported history trace is loaded")
        if trace_index < 0 or trace_index >= len(self.history_trace_snapshots):
            raise HTTPException(status_code=400, detail="History trace step is out of range")
        graph, edit_steps = self.history_trace_snapshots[trace_index]
        self.graph = graph.clone()
        self.edit_steps = copy.deepcopy(edit_steps)
        self.history_trace_index = trace_index
        self.version += 1
        self._clear_auto_repeat_candidates()
        return self.snapshot()

    def restore_operation_state(self, state_index: int) -> Dict[str, Any]:
        self.has_graph()
        if state_index < 0 or state_index >= len(self.operation_states):
            raise HTTPException(status_code=400, detail="Operation state is out of range")
        self._restore_state(self.operation_states[state_index])
        self.undo_stack = [self._clone_state(state) for state in self.operation_states[:state_index]]
        self.redo_stack = [
            self._clone_state(state)
            for state in reversed(self.operation_states[state_index + 1 :])
        ]
        self.active_operation_state_index = state_index
        self.version += 1
        self._clear_auto_repeat_candidates()
        return self.snapshot()

    def clear_operation_history(self) -> Dict[str, Any]:
        self.has_graph()
        self.log.clear()
        self.operation_states.clear()
        self.active_operation_state_index = None
        self._clear_history_trace()
        self.version += 1
        return self.snapshot()

    def _record_edit_step(self, action: str, event_details: Dict[str, Any], result: Dict[str, Any]) -> None:
        if action == "apply_history":
            self.edit_steps.extend(copy.deepcopy(result.get("applied_steps") or []))
            return
        step = history_step_from_event(action, event_details)
        if step is not None:
            self.edit_steps.append(step)

    @staticmethod
    def _event(action: str, details: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "action": action,
            "details": details,
        }

    def _append_log(self, action: str, details: Dict[str, Any]) -> None:
        event = self._event(action, details)
        if self.graph is not None:
            state_index = len(self.operation_states)
            self.active_operation_state_index = state_index
            self.operation_states.append(self._capture_state())
            event["state_index"] = state_index
        self.log.append(event)

    def _capture_state(self) -> SessionState:
        return SessionState(
            graph=self.graph.clone() if self.graph is not None else None,
            edit_steps=copy.deepcopy(self.edit_steps),
            source_name=self.source_name,
            sequence_source_path=self.sequence_source_path,
            sequence_source_name=self.sequence_source_name,
            sequence_source_size=self.sequence_source_size,
            light_mode=self.light_mode,
            light_mode_reason=self.light_mode_reason,
            sequence_load_seconds=self.sequence_load_seconds,
            alignment_hits_by_query=copy.deepcopy(self.alignment_hits_by_query),
            alignment_format=self.alignment_format,
            alignment_target_role=self.alignment_target_role,
            alignment_source_name=self.alignment_source_name,
            alignment_selected_read_id=self.alignment_selected_read_id,
            alignment_last_command=self.alignment_last_command,
            alignment_last_stderr=self.alignment_last_stderr,
            active_operation_state_index=self.active_operation_state_index,
        )

    @staticmethod
    def _clone_state(state: SessionState) -> SessionState:
        return SessionState(
            graph=state.graph.clone() if state.graph is not None else None,
            edit_steps=copy.deepcopy(state.edit_steps),
            source_name=state.source_name,
            sequence_source_path=state.sequence_source_path,
            sequence_source_name=state.sequence_source_name,
            sequence_source_size=state.sequence_source_size,
            light_mode=state.light_mode,
            light_mode_reason=state.light_mode_reason,
            sequence_load_seconds=state.sequence_load_seconds,
            alignment_hits_by_query=copy.deepcopy(state.alignment_hits_by_query),
            alignment_format=state.alignment_format,
            alignment_target_role=state.alignment_target_role,
            alignment_source_name=state.alignment_source_name,
            alignment_selected_read_id=state.alignment_selected_read_id,
            alignment_last_command=state.alignment_last_command,
            alignment_last_stderr=state.alignment_last_stderr,
            active_operation_state_index=state.active_operation_state_index,
        )

    def _restore_state(self, state: SessionState) -> None:
        self.graph = state.graph.clone() if state.graph is not None else None
        self.edit_steps = copy.deepcopy(state.edit_steps)
        self.source_name = state.source_name
        self.sequence_source_path = state.sequence_source_path
        self.sequence_source_name = state.sequence_source_name
        self.sequence_source_size = state.sequence_source_size
        self.light_mode = state.light_mode
        self.light_mode_reason = state.light_mode_reason
        self.sequence_load_seconds = state.sequence_load_seconds
        self.alignment_hits_by_query = copy.deepcopy(state.alignment_hits_by_query)
        self.alignment_format = state.alignment_format
        self.alignment_target_role = state.alignment_target_role
        self.alignment_source_name = state.alignment_source_name
        self.alignment_selected_read_id = state.alignment_selected_read_id
        self.alignment_last_command = state.alignment_last_command
        self.alignment_last_stderr = state.alignment_last_stderr
        self.active_operation_state_index = state.active_operation_state_index
        self._refresh_alignment()

    def _clear_history_trace(self) -> None:
        self.history_trace_snapshots.clear()
        self.history_trace.clear()
        self.history_trace_index = None


session_registry_lock = threading.Lock()
session_registry: Dict[str, EditorSession] = {}
session_last_seen: Dict[str, float] = {}


def normalize_session_id(raw_session_id: Optional[str]) -> str:
    if not raw_session_id:
        return DEFAULT_SESSION_ID
    candidate = raw_session_id.strip()
    if SESSION_ID_RE.fullmatch(candidate):
        return candidate
    return DEFAULT_SESSION_ID


def prune_sessions(now: float) -> None:
    expired_ids = [
        session_id
        for session_id, last_seen in session_last_seen.items()
        if session_id != DEFAULT_SESSION_ID and now - last_seen > SESSION_TTL_SECONDS
    ]
    for session_id in expired_ids:
        session_registry.pop(session_id, None)
        session_last_seen.pop(session_id, None)

    overflow = len(session_registry) - MAX_SESSIONS
    if overflow <= 0:
        return
    removable_ids = sorted(
        (session_id for session_id in session_registry if session_id != DEFAULT_SESSION_ID),
        key=lambda session_id: session_last_seen.get(session_id, 0),
    )
    for session_id in removable_ids[:overflow]:
        session_registry.pop(session_id, None)
        session_last_seen.pop(session_id, None)


def get_editor_session(session_id: str) -> EditorSession:
    now = time.monotonic()
    with session_registry_lock:
        prune_sessions(now)
        if session_id not in session_registry:
            session_registry[session_id] = EditorSession()
        session_last_seen[session_id] = now
        return session_registry[session_id]


class SessionProxy:
    def _target(self) -> EditorSession:
        return get_editor_session(current_session_id.get(DEFAULT_SESSION_ID))

    def __getattr__(self, name: str) -> Any:
        target = self._target()
        attr = getattr(target, name)
        if not callable(attr):
            return attr

        def locked_call(*args: Any, **kwargs: Any) -> Any:
            with target.lock:
                return attr(*args, **kwargs)

        return locked_call


session = SessionProxy()


def server_data_root() -> Path:
    root = SERVER_DATA_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def sequence_cache_root() -> Path:
    root = server_data_root() / CACHE_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_cache_stem(source_name: str) -> str:
    stem = Path(source_name).stem or "uploaded"
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._")
    return cleaned[:80] or "uploaded"


def next_cache_path(source_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return sequence_cache_root() / f"{timestamp}-{uuid.uuid4().hex[:10]}-{safe_cache_stem(source_name)}.raw"


def copy_stream_to_cache(source, source_name: str) -> Path:
    cache_path = next_cache_path(source_name)
    with cache_path.open("wb") as target:
        shutil.copyfileobj(source, target, length=1024 * 1024)
    return cache_path


def cache_upload_file(file: UploadFile, source_name: str) -> Path:
    file.file.seek(0)
    cache_path = copy_stream_to_cache(file.file, source_name)
    file.file.seek(0)
    return cache_path


def cache_local_file(path: Path, source_name: str) -> Path:
    cache_path = next_cache_path(source_name)
    shutil.copyfile(path, cache_path)
    return cache_path


def cache_sftp_file(sftp, remote_path: str, source_name: str) -> Path:
    cache_path = next_cache_path(source_name)
    with sftp.open(remote_path, "rb") as remote_file, cache_path.open("wb") as target:
        while True:
            chunk = remote_file.read(1024 * 1024)
            if not chunk:
                break
            if isinstance(chunk, str):
                chunk = chunk.encode("utf-8", errors="replace")
            target.write(chunk)
    return cache_path


def parse_cached_gfa(
    cache_path: Path,
    source_name: str,
    keep_sequences: bool,
    *,
    keep_other_records: bool = True,
) -> LoadedGfa:
    start = time.monotonic()
    try:
        with cache_path.open("rb") as handle:
            graph = parse_gfa_lines(
                handle,
                keep_sequences=keep_sequences,
                sequence_time_limit_seconds=SEQUENCE_LOAD_TIMEOUT_SECONDS if keep_sequences else None,
                keep_other_records=keep_other_records,
            )
    except ValueError:
        raise
    elapsed = time.monotonic() - start
    light_mode = graph.dropped_sequences
    reason = None
    if keep_sequences and graph.dropped_sequences:
        reason = (
            f"Sequence loading exceeded {SEQUENCE_LOAD_TIMEOUT_SECONDS:g} seconds; "
            "light mode is enabled and sequences will be rebuilt from the original GFA when needed."
        )
    elif not keep_sequences:
        reason = "Light mode is enabled; sequences are stored in the original GFA cache and rebuilt when needed."
    return LoadedGfa(
        graph=graph,
        cache_path=cache_path,
        light_mode=light_mode,
        light_mode_reason=reason,
        sequence_load_seconds=elapsed,
        source_size=cache_path.stat().st_size,
    )


def load_cached_gfa(
    cache_path: Path,
    source_name: str,
    keep_sequences: bool,
    *,
    keep_other_records: bool = True,
) -> LoadedGfa:
    return parse_cached_gfa(
        cache_path,
        source_name,
        keep_sequences,
        keep_other_records=keep_other_records,
    )


def subgraph_from_node_ids(graph: GfaGraph, node_ids: List[str]) -> GfaGraph:
    node_id_set = set(node_ids)
    return GfaGraph(
        headers=copy.deepcopy(graph.headers),
        segments={
            node_id: copy.deepcopy(graph.segments[node_id])
            for node_id in node_ids
            if node_id in node_id_set and node_id in graph.segments
        },
        links=[
            copy.deepcopy(link)
            for link in graph.links
            if link.source in node_id_set and link.target in node_id_set
        ],
        paths=[
            copy.deepcopy(path)
            for path in graph.paths
            if path_record_belongs_to_nodes(path, node_id_set)
        ],
        # hifiasm can emit hundreds of thousands of A records. They are not
        # rendered or exported by the editor, so duplicating them into every
        # split component dominates large-file load time.
        other_records=[],
        dropped_sequences=graph.dropped_sequences,
    )


def path_record_belongs_to_nodes(path: Any, node_ids: set[str]) -> bool:
    path_node_ids = {step.segment for step in path.steps}
    if not path_node_ids or not path_node_ids.issubset(node_ids):
        return False
    repeat_node_tag = path.tags.get("RN")
    repeat_node_id = str(repeat_node_tag.get("value") or repeat_node_tag.get("raw")) if repeat_node_tag else ""
    return not repeat_node_id or repeat_node_id in node_ids


def connected_component_node_sets(graph: GfaGraph) -> List[List[str]]:
    node_order = list(graph.segments.keys())
    adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_order}
    for link in graph.links:
        if link.source not in adjacency or link.target not in adjacency:
            continue
        adjacency[link.source].append(link.target)
        if link.target != link.source:
            adjacency[link.target].append(link.source)

    seen: set[str] = set()
    components: List[List[str]] = []
    for start_id in node_order:
        if start_id in seen:
            continue
        seen.add(start_id)
        stack = [start_id]
        component_set = {start_id}
        while stack:
            node_id = stack.pop()
            for neighbor_id in adjacency[node_id]:
                if neighbor_id in seen:
                    continue
                seen.add(neighbor_id)
                component_set.add(neighbor_id)
                stack.append(neighbor_id)
        components.append([node_id for node_id in node_order if node_id in component_set])
    return components


def count_internal_links(graph: GfaGraph, node_ids: List[str]) -> int:
    node_id_set = set(node_ids)
    return sum(1 for link in graph.links if link.source in node_id_set and link.target in node_id_set)


def make_split_component(
    graph: GfaGraph,
    component_id: str,
    label: str,
    export_suffix: str,
    node_ids: List[str],
    *,
    is_remaining_group: bool = False,
) -> SplitComponentState:
    return SplitComponentState(
        id=component_id,
        label=label,
        export_suffix=export_suffix,
        original_node_ids=list(node_ids),
        is_remaining_group=is_remaining_group,
        graph=subgraph_from_node_ids(graph, node_ids),
    )


def build_split_components(
    graph: GfaGraph,
    *,
    max_elements_per_view: int,
    remaining_chunk_size: int,
    auto_split: bool,
) -> Tuple[List[SplitComponentState], Optional[str]]:
    _ = max_elements_per_view
    remaining_chunk_size = coerce_positive_int(remaining_chunk_size, DEFAULT_REMAINING_CHUNK_SIZE)
    if not auto_split or len(graph.segments) <= DEFAULT_SPLIT_NODE_THRESHOLD:
        return [], None

    raw_components = []
    for node_ids in connected_component_node_sets(graph):
        link_count = count_internal_links(graph, node_ids)
        raw_components.append(
            {
                "node_ids": node_ids,
                "node_count": len(node_ids),
                "link_count": link_count,
                "element_count": len(node_ids) + link_count,
            }
        )
    if not raw_components:
        return [], None

    raw_components.sort(key=lambda item: item["element_count"], reverse=True)
    warning = None
    if len(raw_components) == 1 and raw_components[0]["node_count"] > DEFAULT_SPLIT_NODE_THRESHOLD:
        warning = "This graph contains one large connected component. Splitting by connectivity cannot reduce this component further."

    selected = [component for component in raw_components if component["link_count"] > 1]
    remaining = [component for component in raw_components if component["link_count"] <= 1]

    split_components: List[SplitComponentState] = []
    for index, component in enumerate(selected, start=1):
        split_components.append(
            make_split_component(
                graph,
                f"component_{index:03d}",
                f"Component {index}",
                f"component_{index:03d}",
                component["node_ids"],
            )
        )

    remaining_node_ids = [
        node_id
        for component in remaining
        for node_id in component["node_ids"]
        if node_id in graph.segments
    ]
    remaining_node_ids = sorted(
        dict.fromkeys(remaining_node_ids),
        key=lambda node_id: (-graph.segments[node_id].length, node_id),
    )
    for part_index, offset in enumerate(range(0, len(remaining_node_ids), remaining_chunk_size), start=1):
        chunk_node_ids = remaining_node_ids[offset : offset + remaining_chunk_size]
        if not chunk_node_ids:
            continue
        split_components.append(
            make_split_component(
                graph,
                f"remaining_part_{part_index:03d}",
                f"remaining_part_{part_index}",
                f"remaining_part_{part_index:03d}",
                chunk_node_ids,
                is_remaining_group=True,
            )
        )

    return split_components, warning


def load_uploaded_gfa(
    file: UploadFile,
    source_name: str,
    keep_sequences: bool,
    *,
    keep_other_records: bool = True,
) -> LoadedGfa:
    cache_path = cache_upload_file(file, source_name)
    return load_cached_gfa(
        cache_path,
        source_name,
        keep_sequences,
        keep_other_records=keep_other_records,
    )


def resolve_server_data_path(relative_path: str, *, must_exist: bool = False) -> Path:
    raw_path = Path(relative_path)
    if not relative_path or raw_path.is_absolute():
        raise HTTPException(status_code=400, detail="Server path must be relative to GFA_EDITOR_DATA_DIR")
    root = server_data_root()
    target = (root / raw_path).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Server path cannot leave GFA_EDITOR_DATA_DIR") from exc
    if must_exist and not target.is_file():
        raise HTTPException(status_code=404, detail=f"Server file not found: {relative_path}")
    return target


def default_server_export_path(extension: str) -> str:
    return session.default_server_export_path(extension)


def strip_server_prefix(source_name: str) -> str:
    return source_name[len("server:") :] if source_name.startswith("server:") else source_name


def normalize_export_format(format_value: str) -> str:
    normalized_format = format_value.lower()
    if normalized_format not in {"gfa", "fasta", "fa"}:
        raise HTTPException(status_code=400, detail="Export format must be gfa or fasta")
    return normalized_format


def export_graph_text(format_value: str) -> Tuple[str, str]:
    normalized_format = normalize_export_format(format_value)
    extension = "fasta" if normalized_format in {"fasta", "fa"} else "gfa"
    graph = session.graph_with_sequences()
    try:
        body = export_fasta(graph) if normalized_format in {"fasta", "fa"} else export_gfa(graph)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return extension, body


def export_selected_links_text(format_value: str, edge_ids: List[str]) -> Tuple[str, str]:
    normalized_format = normalize_export_format(format_value)
    graph = session.graph_with_sequences()
    selected_ids = [edge_id for edge_id in dict.fromkeys(edge_ids) if edge_id]
    if not selected_ids:
        raise HTTPException(status_code=400, detail="Select at least one link to export")
    links_by_id = {link.id: link for link in graph.links}
    missing_ids = [edge_id for edge_id in selected_ids if edge_id not in links_by_id]
    if missing_ids:
        raise HTTPException(status_code=404, detail=f"Unknown selected link(s): {', '.join(missing_ids[:5])}")

    selected_links = [copy.deepcopy(links_by_id[edge_id]) for edge_id in selected_ids]
    selected_node_ids = set()
    for link in selected_links:
        selected_node_ids.add(link.source)
        selected_node_ids.add(link.target)
    selected_graph = GfaGraph(
        headers=copy.deepcopy(graph.headers),
        segments={
            node_id: copy.deepcopy(graph.segments[node_id])
            for node_id in graph.segments
            if node_id in selected_node_ids
        },
        links=selected_links,
        dropped_sequences=graph.dropped_sequences,
    )
    extension = "fasta" if normalized_format in {"fasta", "fa"} else "gfa"
    try:
        body = export_fasta(selected_graph) if normalized_format in {"fasta", "fa"} else export_gfa(selected_graph)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return extension, body


def normalize_alignment_tool(tool: str) -> str:
    normalized = tool.lower()
    if normalized not in {"blastn", "minimap2"}:
        raise HTTPException(status_code=400, detail="Alignment tool must be blastn or minimap2")
    return normalized


def executable_path(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise HTTPException(status_code=501, detail=f"{name} is not installed or not on PATH")
    return path


def parse_extra_args(extra_args: str) -> List[str]:
    if not extra_args.strip():
        return []
    try:
        return shlex.split(extra_args)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid alignment args: {exc}") from exc


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


def build_alignment_command(
    tool: str,
    target_fasta: Path,
    query_fasta: Path,
    output_path: Path,
    extra_args: str,
) -> Tuple[List[str], str]:
    normalized_tool = normalize_alignment_tool(tool)
    args = parse_extra_args(extra_args)
    if normalized_tool == "blastn":
        args = strip_arg_values(args, {"-out", "-outfmt"})
        outfmt = "6 qseqid sseqid pident length mismatch gapopen qstart qend sstart send evalue bitscore"
        command = [
            executable_path("blastn"),
            "-query",
            str(query_fasta),
            "-subject",
            str(target_fasta),
            *args,
            "-outfmt",
            outfmt,
            "-out",
            str(output_path),
        ]
        return command, "blast6"

    args = strip_arg_values(args, {"-o"})
    command = [
        executable_path("minimap2"),
        *args,
        str(target_fasta),
        str(query_fasta),
    ]
    return command, "paf"


def run_alignment_command(
    tool: str,
    query_contents: bytes,
    query_filename: str,
    extra_args: str,
) -> Tuple[str, str, str, str]:
    graph = session.graph_with_sequences()
    try:
        target_text = export_fasta(graph)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    suffix = Path(query_filename or "query.fa").suffix or ".fa"
    with tempfile.TemporaryDirectory(prefix="gfa-editor-align-") as temp_dir:
        temp_root = Path(temp_dir)
        target_path = temp_root / "graph.fa"
        query_path = temp_root / f"query{suffix}"
        output_path = temp_root / "alignment.out"
        target_path.write_text(target_text, encoding="utf-8")
        query_path.write_bytes(query_contents)
        command, result_format = build_alignment_command(tool, target_path, query_path, output_path, extra_args)
        try:
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=180,
            )
        except subprocess.TimeoutExpired as exc:
            raise HTTPException(status_code=504, detail=f"Alignment timed out: {shlex.join(command)}") from exc
        if result.returncode != 0:
            stderr = (result.stderr or result.stdout or "").strip()
            raise HTTPException(status_code=502, detail=f"Alignment failed: {stderr or shlex.join(command)}")
        if result_format == "paf":
            output_text = result.stdout
        else:
            output_text = output_path.read_text(encoding="utf-8", errors="replace")
        return result_format, output_text, shlex.join(command), (result.stderr or "").strip()[-2000:]


def require_paramiko():
    try:
        import paramiko  # type: ignore
    except ImportError as exc:
        raise HTTPException(
            status_code=501,
            detail="SFTP requires paramiko. Install dependencies with: python -m pip install -r backend/requirements.txt",
        ) from exc
    return paramiko


def open_sftp_client(payload: "SftpTransferRequest"):
    if not payload.host.strip():
        raise HTTPException(status_code=400, detail="SFTP host is required")
    if not payload.username.strip():
        raise HTTPException(status_code=400, detail="SFTP username is required")
    if not payload.remote_path.strip().startswith("/"):
        raise HTTPException(status_code=400, detail="SFTP remote path must be an absolute path")
    paramiko = require_paramiko()
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            payload.host.strip(),
            port=int(payload.port),
            username=payload.username.strip(),
            password=payload.password or None,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
        )
        return client, client.open_sftp()
    except Exception as exc:
        client.close()
        raise HTTPException(status_code=502, detail=f"SFTP connection failed: {exc}") from exc


def ensure_remote_parent_dirs(sftp, remote_path: str) -> None:
    parent = posixpath.dirname(remote_path)
    if not parent or parent == "/":
        return
    parts = [part for part in parent.split("/") if part]
    current = ""
    for part in parts:
        current = f"{current}/{part}"
        try:
            sftp.stat(current)
        except OSError:
            sftp.mkdir(current)


class NodeRequest(BaseModel):
    node_id: str
    new_id: Optional[str] = None


class RepeatResolutionRequest(BaseModel):
    node_id: str
    duplicate_id: str
    strategy: str


class EdgeRequest(BaseModel):
    edge_id: str


class MergeSelectionRequest(BaseModel):
    node_ids: Optional[List[str]] = None
    edge_ids: Optional[List[str]] = None


class DeleteSelectionRequest(BaseModel):
    node_ids: Optional[List[str]] = None
    edge_ids: Optional[List[str]] = None


class RotateCircularNodeRequest(BaseModel):
    node_id: str
    offset: int


class HistoryTraceStepRequest(BaseModel):
    trace_index: int


class OperationStateRequest(BaseModel):
    state_index: int


class EditStepJumpRequest(BaseModel):
    target_step_count: int


class NodeUpdateRequest(BaseModel):
    node_id: str
    name: Optional[str] = None
    label: Optional[str] = None
    color: Optional[str] = None
    depth: Optional[float] = None


class EdgeUpdateRequest(BaseModel):
    edge_id: str
    label: Optional[str] = None
    color: Optional[str] = None
    support: Optional[float] = None
    cigar: Optional[str] = None


class ServerFileRequest(BaseModel):
    path: str
    keep_sequences: bool = False
    auto_split: bool = True
    max_elements_per_view: int = DEFAULT_SPLIT_MAX_ELEMENTS
    remaining_chunk_size: int = DEFAULT_REMAINING_CHUNK_SIZE


class ServerSaveRequest(BaseModel):
    path: Optional[str] = None
    format: str = "gfa"


class SelectionExportRequest(BaseModel):
    edge_ids: List[str]
    format: str = "gfa"


class AlignmentReadSelectionRequest(BaseModel):
    read_id: Optional[str] = None


class ComponentSelectionRequest(BaseModel):
    component_id: str


class AutoRepeatResolutionApplyRequest(BaseModel):
    candidate_id: str


class SftpTransferRequest(BaseModel):
    host: str
    port: int = 22
    username: str
    password: Optional[str] = None
    remote_path: str
    keep_sequences: bool = True
    auto_split: bool = True
    max_elements_per_view: int = DEFAULT_SPLIT_MAX_ELEMENTS
    remaining_chunk_size: int = DEFAULT_REMAINING_CHUNK_SIZE
    format: str = "gfa"


app = FastAPI(
    title="GFA Editor v1.3.2",
    description="A local Bandage-style GFA graph editor.",
    version="1.3.2",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def bind_editor_session(request: Request, call_next):
    raw_session_id = (
        request.headers.get(SESSION_HEADER)
        or request.query_params.get("gfa_session")
        or request.query_params.get("session")
        or request.cookies.get(SESSION_COOKIE)
    )
    session_id = normalize_session_id(raw_session_id)
    token = current_session_id.set(session_id)
    try:
        response = await call_next(request)
        response.headers[SESSION_HEADER] = session_id
        return response
    finally:
        current_session_id.reset(token)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "version": "1.3.2", "instance_id": INSTANCE_ID}


@app.post("/api/upload")
async def upload_gfa(
    file: UploadFile = File(...),
    keep_sequences: bool = Form(False),
    auto_split: bool = Form(True),
    max_elements_per_view: int = Form(DEFAULT_SPLIT_MAX_ELEMENTS),
    remaining_chunk_size: int = Form(DEFAULT_REMAINING_CHUNK_SIZE),
) -> Dict[str, Any]:
    source_name = file.filename or "uploaded.gfa"
    try:
        loaded = await asyncio.to_thread(
            load_uploaded_gfa,
            file,
            source_name,
            keep_sequences,
            keep_other_records=not auto_split,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.load(
        loaded.graph,
        source_name,
        sequence_source_path=loaded.cache_path,
        sequence_source_size=loaded.source_size,
        light_mode=loaded.light_mode,
        light_mode_reason=loaded.light_mode_reason,
        sequence_load_seconds=loaded.sequence_load_seconds,
        auto_split=auto_split,
        max_elements_per_view=max_elements_per_view,
        remaining_chunk_size=remaining_chunk_size,
    )


@app.get("/api/graph")
def get_graph(include_sequences: bool = False) -> Dict[str, Any]:
    return session.snapshot(include_sequences=include_sequences)


@app.get("/api/server_files")
def list_server_files() -> Dict[str, Any]:
    root = server_data_root()
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SERVER_FILE_EXTENSIONS:
            continue
        stat = path.stat()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "name": path.name,
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
            }
        )
    return {
        "data_dir": str(root),
        "files": files,
    }


@app.post("/api/load_server_file")
def load_server_file(payload: ServerFileRequest) -> Dict[str, Any]:
    path = resolve_server_data_path(payload.path, must_exist=True)
    if path.suffix.lower() not in SERVER_FILE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Server file must be .gfa or .txt")
    relative_path = path.relative_to(server_data_root()).as_posix()
    source_name = f"server:{relative_path}"
    try:
        cache_path = cache_local_file(path, relative_path)
        loaded = load_cached_gfa(
            cache_path,
            source_name,
            payload.keep_sequences,
            keep_other_records=not payload.auto_split,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.load(
        loaded.graph,
        source_name,
        sequence_source_path=loaded.cache_path,
        sequence_source_size=loaded.source_size,
        light_mode=loaded.light_mode,
        light_mode_reason=loaded.light_mode_reason,
        sequence_load_seconds=loaded.sequence_load_seconds,
        auto_split=payload.auto_split,
        max_elements_per_view=payload.max_elements_per_view,
        remaining_chunk_size=payload.remaining_chunk_size,
    )


@app.post("/api/select_component")
def select_component(payload: ComponentSelectionRequest) -> Dict[str, Any]:
    return session.select_split_component(payload.component_id)


@app.post("/api/save_server_file")
def save_server_file(payload: ServerSaveRequest) -> Dict[str, Any]:
    extension, body = export_graph_text(payload.format)
    relative_path = payload.path.strip() if payload.path else default_server_export_path(extension)
    if not Path(relative_path).suffix:
        relative_path = f"{relative_path}.{extension}"
    path = resolve_server_data_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    saved_relative_path = path.relative_to(server_data_root()).as_posix()
    return {
        "path": saved_relative_path,
        "format": extension,
        "bytes": len(body.encode("utf-8")),
    }


@app.post("/api/sftp_download")
def sftp_download(payload: SftpTransferRequest) -> Dict[str, Any]:
    client, sftp = open_sftp_client(payload)
    source_name = f"sftp:{payload.host.strip()}:{payload.remote_path.strip()}"
    try:
        cache_path = cache_sftp_file(sftp, payload.remote_path.strip(), payload.remote_path.strip())
        loaded = load_cached_gfa(
            cache_path,
            source_name,
            payload.keep_sequences,
            keep_other_records=not payload.auto_split,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"SFTP download failed: {exc}") from exc
    finally:
        sftp.close()
        client.close()
    return session.load(
        loaded.graph,
        source_name,
        sequence_source_path=loaded.cache_path,
        sequence_source_size=loaded.source_size,
        light_mode=loaded.light_mode,
        light_mode_reason=loaded.light_mode_reason,
        sequence_load_seconds=loaded.sequence_load_seconds,
        auto_split=payload.auto_split,
        max_elements_per_view=payload.max_elements_per_view,
        remaining_chunk_size=payload.remaining_chunk_size,
    )


@app.post("/api/sftp_upload")
def sftp_upload(payload: SftpTransferRequest) -> Dict[str, Any]:
    extension, body = export_graph_text(payload.format)
    remote_path = payload.remote_path.strip()
    if not posixpath.basename(remote_path):
        remote_path = posixpath.join(remote_path, default_server_export_path(extension))
    if not posixpath.splitext(remote_path)[1]:
        remote_path = f"{remote_path}.{extension}"
    client, sftp = open_sftp_client(payload)
    try:
        ensure_remote_parent_dirs(sftp, remote_path)
        with sftp.open(remote_path, "w") as remote_file:
            remote_file.write(body)
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"SFTP upload failed: {exc}") from exc
    finally:
        sftp.close()
        client.close()
    return {
        "remote_path": remote_path,
        "format": extension,
        "bytes": len(body.encode("utf-8")),
    }


@app.post("/api/delete_node/{node_id}")
def api_delete_node(node_id: str) -> Dict[str, Any]:
    try:
        return session.mutate(
            "delete_node",
            {"node_id": node_id},
            lambda graph: delete_node(graph, node_id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/delete_node")
def api_delete_node_json(payload: NodeRequest) -> Dict[str, Any]:
    return api_delete_node(payload.node_id)


@app.post("/api/delete_edge/{edge_id}")
def api_delete_edge(edge_id: str) -> Dict[str, Any]:
    try:
        return session.mutate(
            "delete_edge",
            {"edge_id": edge_id},
            lambda graph: delete_edge(graph, edge_id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/delete_edge")
def api_delete_edge_json(payload: EdgeRequest) -> Dict[str, Any]:
    return api_delete_edge(payload.edge_id)


@app.post("/api/delete_selection")
def api_delete_selection(payload: DeleteSelectionRequest) -> Dict[str, Any]:
    node_ids = payload.node_ids or []
    edge_ids = payload.edge_ids or []
    try:
        return session.mutate(
            "delete_selection",
            {"node_ids": node_ids, "edge_ids": edge_ids},
            lambda graph: delete_selection(graph, node_ids, edge_ids),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/merge_link")
def api_merge_link(payload: EdgeRequest) -> Dict[str, Any]:
    try:
        return session.mutate(
            "merge_link",
            {"edge_id": payload.edge_id},
            lambda graph: merge_link(graph, payload.edge_id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/merge_selection")
def api_merge_selection(payload: MergeSelectionRequest) -> Dict[str, Any]:
    node_ids = payload.node_ids or []
    edge_ids = payload.edge_ids or []
    try:
        return session.mutate(
            "merge_selection",
            {"node_ids": node_ids, "edge_ids": edge_ids},
            lambda graph: merge_selection(graph, node_ids, edge_ids),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/rotate_circular_node")
def api_rotate_circular_node(payload: RotateCircularNodeRequest) -> Dict[str, Any]:
    def rotate_with_light_mode_fallback(graph: GfaGraph) -> Dict[str, Any]:
        try:
            return rotate_circular_node(graph, payload.node_id, payload.offset)
        except ValueError as exc:
            if "requires loading" not in str(exc) or not graph.dropped_sequences:
                raise
            rebuilt_graph = session.graph_with_sequences()
            return rotate_circular_node(rebuilt_graph, payload.node_id, payload.offset)

    try:
        return session.mutate(
            "rotate_circular_node",
            payload.model_dump(),
            rotate_with_light_mode_fallback,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/duplicate_node/{node_id}")
def api_duplicate_node(node_id: str, new_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        return session.mutate(
            "duplicate_node",
            {"node_id": node_id, "requested_id": new_id},
            lambda graph: duplicate_node(graph, node_id, new_id),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/duplicate_node")
def api_duplicate_node_json(payload: NodeRequest) -> Dict[str, Any]:
    return api_duplicate_node(payload.node_id, payload.new_id)


@app.post("/api/repeat_resolution")
def api_repeat_resolution(payload: RepeatResolutionRequest) -> Dict[str, Any]:
    try:
        return session.mutate(
            "repeat_resolution",
            payload.model_dump(),
            lambda graph: repeat_resolve_node(graph, payload.node_id, payload.duplicate_id, payload.strategy),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auto_repeat_resolution_candidates")
def api_auto_repeat_resolution_candidates() -> Dict[str, Any]:
    try:
        return session.generate_auto_repeat_resolution_candidates()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/apply_auto_repeat_resolution")
def api_apply_auto_repeat_resolution(payload: AutoRepeatResolutionApplyRequest) -> Dict[str, Any]:
    try:
        return session.apply_auto_repeat_resolution_candidate(payload.candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/update_node")
def api_update_node(payload: NodeUpdateRequest) -> Dict[str, Any]:
    try:
        return session.mutate(
            "update_node",
            payload.model_dump(exclude_none=True),
            lambda graph: update_node(
                graph,
                payload.node_id,
                name=payload.name,
                label=payload.label,
                color=payload.color,
                depth=payload.depth,
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/update_edge")
def api_update_edge(payload: EdgeUpdateRequest) -> Dict[str, Any]:
    try:
        return session.mutate(
            "update_edge",
            payload.model_dump(exclude_none=True),
            lambda graph: update_edge(
                graph,
                payload.edge_id,
                label=payload.label,
                color=payload.color,
                support=payload.support,
                cigar=payload.cigar,
            ),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/undo")
def api_undo() -> Dict[str, Any]:
    return session.undo()


@app.post("/api/redo")
def api_redo() -> Dict[str, Any]:
    return session.redo()


@app.post("/api/upload_blast")
async def upload_blast(file: UploadFile = File(...)) -> Dict[str, Any]:
    try:
        contents = await file.read()
        hits_by_query = parse_blast_outfmt6(contents.decode("utf-8", errors="replace"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.mutate(
        "upload_blast",
        {"source_name": file.filename or "blast.tsv"},
        lambda graph: attach_blast_hits(graph, hits_by_query, target_role="query", source_name=file.filename or "blast.tsv"),
    )


@app.post("/api/upload_alignment")
async def upload_alignment(
    file: UploadFile = File(...),
    format: str = Form("blast6"),
    target_role: str = Form("subject"),
) -> Dict[str, Any]:
    if target_role not in {"query", "subject"}:
        raise HTTPException(status_code=400, detail="Alignment target role must be query or subject")
    try:
        contents = await file.read()
        hits_by_query = parse_alignment_text(contents.decode("utf-8", errors="replace"), format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    source_name = file.filename or f"alignment.{format}"
    return session.apply_alignment(
        hits_by_query,
        format=format,
        target_role=target_role,
        source_name=source_name,
    )


@app.post("/api/run_alignment")
async def run_alignment(
    query_file: UploadFile = File(...),
    tool: str = Form("minimap2"),
    extra_args: str = Form(""),
    target_role: str = Form("subject"),
) -> Dict[str, Any]:
    if target_role not in {"query", "subject"}:
        raise HTTPException(status_code=400, detail="Alignment target role must be query or subject")
    query_contents = await query_file.read()
    result_format, output_text, command, stderr = run_alignment_command(
        tool,
        query_contents,
        query_file.filename or "query.fa",
        extra_args,
    )
    try:
        hits_by_query = parse_alignment_text(output_text, result_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Alignment output could not be parsed: {exc}") from exc
    return session.apply_alignment(
        hits_by_query,
        format=result_format,
        target_role=target_role,
        source_name=f"{query_file.filename or 'query.fa'} via {tool}",
        command=command,
        stderr=stderr,
    )


@app.post("/api/alignment_select_read")
def alignment_select_read(payload: AlignmentReadSelectionRequest) -> Dict[str, Any]:
    return session.select_alignment_read(payload.read_id)


@app.get("/api/history")
def history() -> Dict[str, Any]:
    session.has_graph()
    return {
        "version": session.version,
        "can_undo": bool(session.undo_stack),
        "can_redo": bool(session.redo_stack),
        "edit_step_count": len(session.edit_steps),
        "history_trace": session.history_trace,
        "history_trace_index": session.history_trace_index,
        "operation_state_index": session.active_operation_state_index,
        "history": session.log,
    }


@app.get("/api/export_history")
def api_export_history() -> Dict[str, Any]:
    return session.export_history()


@app.post("/api/apply_history")
async def api_apply_history(history_file: UploadFile = File(...)) -> Dict[str, Any]:
    try:
        history_document = json.loads((await history_file.read()).decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid history JSON: {exc}") from exc
    try:
        return session.apply_history_document(history_document, history_file.filename or "history.json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/history_trace_step")
def api_history_trace_step(payload: HistoryTraceStepRequest) -> Dict[str, Any]:
    return session.restore_history_trace_step(payload.trace_index)


@app.post("/api/operation_state")
def api_operation_state(payload: OperationStateRequest) -> Dict[str, Any]:
    return session.restore_operation_state(payload.state_index)


@app.post("/api/clear_operation_history")
def api_clear_operation_history() -> Dict[str, Any]:
    return session.clear_operation_history()


@app.post("/api/jump_edit_step")
def api_jump_edit_step(payload: EditStepJumpRequest) -> Dict[str, Any]:
    return session.jump_edit_step(payload.target_step_count)


@app.post("/api/render_history", response_class=PlainTextResponse)
async def api_render_history(
    gfa_file: UploadFile = File(...),
    history_file: UploadFile = File(...),
    keep_sequences: bool = Form(True),
) -> PlainTextResponse:
    try:
        graph = parse_gfa_text((await gfa_file.read()).decode("utf-8", errors="replace"), keep_sequences=keep_sequences)
        history_document = json.loads((await history_file.read()).decode("utf-8", errors="replace"))
        apply_edit_history(graph, history_document)
        body = export_gfa(graph)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid history JSON: {exc}") from exc
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PlainTextResponse(body, media_type="text/plain")


@app.post("/api/infer_history")
async def api_infer_history(
    old_gfa_file: UploadFile = File(...),
    new_gfa_file: UploadFile = File(...),
    keep_sequences: bool = Form(True),
) -> Dict[str, Any]:
    try:
        old_graph = parse_gfa_text((await old_gfa_file.read()).decode("utf-8", errors="replace"), keep_sequences=keep_sequences)
        new_graph = parse_gfa_text((await new_gfa_file.read()).decode("utf-8", errors="replace"), keep_sequences=keep_sequences)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return infer_edit_history(old_graph, new_graph, source_name=old_gfa_file.filename or "old.gfa")


@app.get("/api/export", response_class=PlainTextResponse)
def api_export(format: str = "gfa") -> PlainTextResponse:
    extension, body = export_graph_text(format)
    filename = session.default_export_filename(extension)
    return PlainTextResponse(
        body,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export_selection", response_class=PlainTextResponse)
def api_export_selection(payload: SelectionExportRequest) -> PlainTextResponse:
    extension, body = export_selected_links_text(payload.format, payload.edge_ids)
    filename = session.default_export_filename(extension, selection=True)
    return PlainTextResponse(
        body,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
