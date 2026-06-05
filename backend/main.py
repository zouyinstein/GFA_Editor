from __future__ import annotations

import copy
from datetime import datetime, timezone
import io
import json
import os
import posixpath
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .gfa_core import (
    GfaGraph,
    attach_blast_hits,
    delete_edge,
    delete_node,
    duplicate_node,
    export_fasta,
    export_gfa,
    merge_link,
    merge_selection,
    parse_alignment_text,
    parse_blast_outfmt6,
    parse_gfa_text,
    repeat_resolve_node,
    rotate_circular_node,
    update_edge,
    update_node,
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
SERVER_FILE_EXTENSIONS = {".gfa", ".txt"}


class EditorSession:
    def __init__(self) -> None:
        self.graph: Optional[GfaGraph] = None
        self.undo_stack: List[Tuple[GfaGraph, List[Dict[str, Any]]]] = []
        self.redo_stack: List[Tuple[GfaGraph, List[Dict[str, Any]]]] = []
        self.log: List[Dict[str, Any]] = []
        self.edit_steps: List[Dict[str, Any]] = []
        self.history_trace_snapshots: List[Tuple[GfaGraph, List[Dict[str, Any]]]] = []
        self.history_trace: List[Dict[str, Any]] = []
        self.history_trace_index: Optional[int] = None
        self.version = 0
        self.source_name: Optional[str] = None
        self.alignment_hits_by_query: Dict[str, List[Dict[str, Any]]] = {}
        self.alignment_format: Optional[str] = None
        self.alignment_target_role: str = "subject"
        self.alignment_source_name: Optional[str] = None
        self.alignment_selected_read_id: Optional[str] = None
        self.alignment_last_command: Optional[str] = None
        self.alignment_last_stderr: Optional[str] = None

    def has_graph(self) -> GfaGraph:
        if self.graph is None:
            raise HTTPException(status_code=409, detail="No GFA graph is loaded")
        return self.graph

    def load(self, graph: GfaGraph, source_name: str) -> Dict[str, Any]:
        self.graph = graph
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.edit_steps.clear()
        self._clear_history_trace()
        self._clear_alignment()
        self.log = [self._event("upload", {"source_name": source_name, "edit_step_count": 0})]
        self.version = 1
        self.source_name = source_name
        return self.snapshot()

    def snapshot(self, include_sequences: bool = False) -> Dict[str, Any]:
        graph = self.has_graph()
        payload = graph.to_client(include_sequences=include_sequences)
        payload["session"] = {
            "version": self.version,
            "source_name": self.source_name,
            "can_undo": bool(self.undo_stack),
            "can_redo": bool(self.redo_stack),
            "edit_step_count": len(self.edit_steps),
            "history": self.log[-30:],
            "history_trace": self.history_trace,
            "history_trace_index": self.history_trace_index,
            "alignment": self.alignment_summary(),
        }
        return payload

    def mutate(self, action: str, details: Dict[str, Any], callback) -> Dict[str, Any]:
        graph = self.has_graph()
        self.undo_stack.append((graph.clone(), copy.deepcopy(self.edit_steps)))
        self.redo_stack.clear()
        try:
            result = callback(graph)
        except Exception:
            self.graph, self.edit_steps = self.undo_stack.pop()
            raise
        event_details = {**details, **(result or {})}
        self._record_edit_step(action, event_details, result or {})
        event_details["edit_step_count"] = len(self.edit_steps)
        self.version += 1
        self.log.append(self._event(action, event_details))
        self._refresh_alignment()
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
        self.alignment_hits_by_query = copy.deepcopy(hits_by_query)
        self.alignment_format = format
        self.alignment_target_role = target_role
        self.alignment_source_name = source_name
        self.alignment_selected_read_id = None
        self.alignment_last_command = command
        self.alignment_last_stderr = stderr
        result = self._refresh_alignment()
        self.version += 1
        self.log.append(
            self._event(
                "alignment",
                {
                    "source_name": source_name,
                    "format": format,
                    "target_role": target_role,
                    "read_count": len(self.alignment_hits_by_query),
                    **result,
                },
            )
        )
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
            *[len(edit_steps) for _, edit_steps in self.undo_stack],
            *[len(edit_steps) for _, edit_steps in self.redo_stack],
        }
        if target_step_count not in reachable_steps:
            raise HTTPException(status_code=409, detail="Target step is not reachable from undo/redo history")
        while len(self.edit_steps) > target_step_count:
            self._undo_once(record_log=False)
        while len(self.edit_steps) < target_step_count:
            self._redo_once(record_log=False)
        return self.snapshot()

    def _undo_once(self, record_log: bool) -> None:
        graph = self.has_graph()
        if not self.undo_stack:
            raise HTTPException(status_code=409, detail="Nothing to undo")
        self.redo_stack.append((graph.clone(), copy.deepcopy(self.edit_steps)))
        self.graph, self.edit_steps = self.undo_stack.pop()
        self.version += 1
        if record_log:
            self.log.append(self._event("undo", {"edit_step_count": len(self.edit_steps)}))

    def _redo_once(self, record_log: bool) -> None:
        graph = self.has_graph()
        if not self.redo_stack:
            raise HTTPException(status_code=409, detail="Nothing to redo")
        self.undo_stack.append((graph.clone(), copy.deepcopy(self.edit_steps)))
        self.graph, self.edit_steps = self.redo_stack.pop()
        self.version += 1
        if record_log:
            self.log.append(self._event("redo", {"edit_step_count": len(self.edit_steps)}))

    def export_history(self) -> Dict[str, Any]:
        self.has_graph()
        return build_history_document(self.edit_steps, source_name=self.source_name)

    def apply_history_document(self, history_document: Dict[str, Any], history_name: str) -> Dict[str, Any]:
        graph = self.has_graph()
        steps = history_document.get("steps")
        if not isinstance(steps, list):
            raise ValueError("History file must contain a steps list")

        self.undo_stack.append((graph.clone(), copy.deepcopy(self.edit_steps)))
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
            self.graph, self.edit_steps = self.undo_stack.pop()
            self._clear_history_trace()
            raise

        self.edit_steps = cumulative_steps
        self.history_trace_snapshots = trace_snapshots
        self.history_trace = trace_entries
        self.history_trace_index = len(trace_entries) - 1
        self.version += 1
        self.log.append(self._event("import_history", {"history_name": history_name, "step_count": len(steps)}))
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
        return self.snapshot()

    def clear_operation_history(self) -> Dict[str, Any]:
        self.has_graph()
        self.log.clear()
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

    def _clear_history_trace(self) -> None:
        self.history_trace_snapshots.clear()
        self.history_trace.clear()
        self.history_trace_index = None


session = EditorSession()


def server_data_root() -> Path:
    root = SERVER_DATA_DIR.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


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
    source_name = strip_server_prefix(session.source_name or "edited")
    source_path = Path(source_name)
    stem = source_path.stem or "edited"
    return f"{stem}.edited.{extension}"


def strip_server_prefix(source_name: str) -> str:
    return source_name[len("server:") :] if source_name.startswith("server:") else source_name


def normalize_export_format(format_value: str) -> str:
    normalized_format = format_value.lower()
    if normalized_format not in {"gfa", "fasta", "fa"}:
        raise HTTPException(status_code=400, detail="Export format must be gfa or fasta")
    return normalized_format


def export_graph_text(format_value: str) -> Tuple[str, str]:
    graph = session.has_graph()
    normalized_format = normalize_export_format(format_value)
    extension = "fasta" if normalized_format in {"fasta", "fa"} else "gfa"
    try:
        body = export_fasta(graph) if normalized_format in {"fasta", "fa"} else export_gfa(graph)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return extension, body


def export_selected_links_text(format_value: str, edge_ids: List[str]) -> Tuple[str, str]:
    graph = session.has_graph()
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
    normalized_format = normalize_export_format(format_value)
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
    graph = session.has_graph()
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


class RotateCircularNodeRequest(BaseModel):
    node_id: str
    offset: int


class HistoryTraceStepRequest(BaseModel):
    trace_index: int


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


class ServerSaveRequest(BaseModel):
    path: Optional[str] = None
    format: str = "gfa"


class SelectionExportRequest(BaseModel):
    edge_ids: List[str]
    format: str = "gfa"


class AlignmentReadSelectionRequest(BaseModel):
    read_id: Optional[str] = None


class SftpTransferRequest(BaseModel):
    host: str
    port: int = 22
    username: str
    password: Optional[str] = None
    remote_path: str
    keep_sequences: bool = True
    format: str = "gfa"


app = FastAPI(
    title="GFA Editor v1.0",
    description="A local Bandage-style GFA graph editor.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/upload")
async def upload_gfa(
    file: UploadFile = File(...),
    keep_sequences: bool = Form(False),
) -> Dict[str, Any]:
    try:
        contents = await file.read()
        graph = parse_gfa_text(contents.decode("utf-8", errors="replace"), keep_sequences=keep_sequences)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return session.load(graph, file.filename or "uploaded.gfa")


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
    try:
        graph = parse_gfa_text(path.read_text(encoding="utf-8", errors="replace"), keep_sequences=payload.keep_sequences)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    relative_path = path.relative_to(server_data_root()).as_posix()
    return session.load(graph, f"server:{relative_path}")


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
    try:
        with sftp.open(payload.remote_path.strip(), "r") as remote_file:
            raw = remote_file.read()
        if isinstance(raw, bytes):
            text = raw.decode("utf-8", errors="replace")
        else:
            text = str(raw)
        graph = parse_gfa_text(text, keep_sequences=payload.keep_sequences)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=502, detail=f"SFTP download failed: {exc}") from exc
    finally:
        sftp.close()
        client.close()
    return session.load(graph, f"sftp:{payload.host.strip()}:{payload.remote_path.strip()}")


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
    try:
        return session.mutate(
            "rotate_circular_node",
            payload.model_dump(),
            lambda graph: rotate_circular_node(graph, payload.node_id, payload.offset),
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
    filename = f"edited.{extension}"
    if session.source_name:
        stem = Path(strip_server_prefix(session.source_name)).stem
        filename = f"{stem}.edited.{extension}"
    return PlainTextResponse(
        body,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/export_selection", response_class=PlainTextResponse)
def api_export_selection(payload: SelectionExportRequest) -> PlainTextResponse:
    extension, body = export_selected_links_text(payload.format, payload.edge_ids)
    filename = f"selected-links.{extension}"
    if session.source_name:
        stem = Path(strip_server_prefix(session.source_name)).stem
        filename = f"{stem}.selected-links.{extension}"
    return PlainTextResponse(
        body,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
