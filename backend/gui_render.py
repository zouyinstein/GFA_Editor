# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Yi Zou <zouyi.nju@gmail.com> and GFA Editor contributors

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Optional
from uuid import uuid4


class GuiRenderUnavailable(RuntimeError):
    pass


def render_with_gui_export(
    input_path: Path,
    output_path: Path,
    *,
    colour: str,
    show_labels: bool,
    query_path: Optional[Path] = None,
    alignment_path: Optional[Path] = None,
    alignment_format: str = "blast6",
    alignment_tool: str = "auto",
    alignment_args: str = "",
    target_role: str = "subject",
    timeout: float = 240.0,
) -> None:
    suffix = output_path.suffix.lower()
    if suffix not in {".pdf", ".svg"}:
        raise GuiRenderUnavailable("GUI export is available for PDF/SVG outputs")
    try:
        import webview  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on desktop extras
        raise GuiRenderUnavailable("pywebview is not installed") from exc

    with tempfile.TemporaryDirectory(prefix="gfa-editor-gui-render-") as temp_dir:
        temp_root = Path(temp_dir)
        data_root = temp_root / "server_data"
        data_root.mkdir(parents=True, exist_ok=True)
        staged_name = safe_stage_name(input_path)
        staged_path = data_root / staged_name
        shutil.copyfile(input_path, staged_path)

        previous_data_dir = os.environ.get("GFA_EDITOR_DATA_DIR")
        os.environ["GFA_EDITOR_DATA_DIR"] = str(data_root)
        try:
            from desktop_app import find_available_port, start_server, wait_for_health

            port = find_available_port(8700)
            server, thread = start_server(port)
            session_id = f"cli-{uuid4().hex}"
            health_url = f"http://127.0.0.1:{port}"
            base_url = f"{health_url}?session={session_id}"
            if not wait_for_health(health_url, timeout=10.0):
                raise GuiRenderUnavailable("GUI export server did not become ready")

            result: dict[str, object] = {}
            window = webview.create_window(
                "GFA Editor CLI render",
                url=base_url,
                width=1282,
                height=1536,
                hidden=True,
                resizable=False,
            )

            def run_export() -> None:
                try:
                    result["data"] = evaluate_export_js(
                        window,
                        staged_name,
                        suffix=suffix,
                        colour=colour,
                        show_labels=show_labels,
                        query_path=query_path,
                        alignment_path=alignment_path,
                        alignment_format=alignment_format,
                        alignment_tool=alignment_tool,
                        alignment_args=alignment_args,
                        target_role=target_role,
                        timeout=timeout,
                    )
                except Exception as exc:  # pragma: no cover - exercised through CLI
                    result["error"] = exc
                finally:
                    try:
                        window.destroy()
                    except Exception:
                        pass

            webview.start(run_export, private_mode=True, debug=False)
            server.should_exit = True
            thread.join(timeout=3.0)

            if "error" in result:
                raise GuiRenderUnavailable(str(result["error"]))
            encoded = result.get("data")
            if not isinstance(encoded, str) or not encoded:
                raise GuiRenderUnavailable("GUI export returned no data")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if suffix == ".svg":
                output_path.write_text(base64.b64decode(encoded).decode("utf-8"), encoding="utf-8")
            else:
                output_path.write_bytes(base64.b64decode(encoded))
        finally:
            if previous_data_dir is None:
                os.environ.pop("GFA_EDITOR_DATA_DIR", None)
            else:
                os.environ["GFA_EDITOR_DATA_DIR"] = previous_data_dir


def safe_stage_name(path: Path) -> str:
    suffix = path.suffix or ".gfa"
    stem = path.stem or "graph"
    return f"{stem}.{uuid4().hex[:8]}{suffix}"


def evaluate_export_js(
    window,
    staged_name: str,
    *,
    suffix: str,
    colour: str,
    show_labels: bool,
    query_path: Optional[Path],
    alignment_path: Optional[Path],
    alignment_format: str,
    alignment_tool: str,
    alignment_args: str,
    target_role: str,
    timeout: float,
) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = window.evaluate_js(
            "document.readyState === 'complete' && "
            "typeof renderGraph === 'function' && "
            "typeof buildGraphSvgExport === 'function' && "
            "typeof buildPdfFromSvg === 'function'"
        )
        if ready:
            break
        time.sleep(0.1)
    else:
        raise TimeoutError("Timed out waiting for GUI renderer")

    color_mode = gui_colour_mode(colour)
    svg_output = str(suffix == ".svg").lower()
    query_payload = file_payload(query_path) if query_path else None
    alignment_payload = file_payload(alignment_path) if alignment_path else None
    tool = gui_alignment_tool(alignment_tool) if query_payload else "minimap2"
    js = f"""
    window.__gfaCliExportResult = null;
    (async () => {{
      try {{
        const response = await apiFetch('/api/load_server_file', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{
            path: {staged_name!r},
            keep_sequences: false,
            auto_split: false
          }})
        }});
        if (!response.ok) {{
          throw new Error(await response.text());
        }}
        const payload = await response.json();
        currentLayout = 'bandage_native';
        if (dom.colorMode) dom.colorMode.value = {color_mode!r};
        if (dom.labelName) dom.labelName.checked = {str(bool(show_labels)).lower()};
        if (dom.showLinkLabels) dom.showLinkLabels.checked = {str(bool(show_labels)).lower()};
        if (dom.labelLength) dom.labelLength.checked = false;
        if (dom.labelDepth) dom.labelDepth.checked = false;
        if (dom.labelBlast) dom.labelBlast.checked = false;
        if (dom.textOutline) dom.textOutline.checked = true;
        if (dom.alignmentShowBackground) dom.alignmentShowBackground.checked = true;
        if (dom.nodeWidth) dom.nodeWidth.value = '18';
        if (dom.linkWidthScale) dom.linkWidthScale.value = '1';
        renderGraph(payload, {{ relayout: true }});
        await new Promise((resolve) => setTimeout(resolve, 80));
        function base64ToBytes(encoded) {{
          const binary = atob(encoded);
          const bytes = new Uint8Array(binary.length);
          for (let index = 0; index < binary.length; index += 1) {{
            bytes[index] = binary.charCodeAt(index);
          }}
          return bytes;
        }}
        async function importAlignmentFile(filePayload) {{
          const formData = new FormData();
          formData.append('file', new File(
            [base64ToBytes(filePayload.data)],
            filePayload.name,
            {{ type: 'text/plain' }}
          ));
          formData.append('format', {alignment_format!r});
          formData.append('target_role', {target_role!r});
          const alignResponse = await apiFetch('/api/upload_alignment', {{
            method: 'POST',
            body: formData
          }});
          if (!alignResponse.ok) {{
            throw new Error(await alignResponse.text());
          }}
          return alignResponse.json();
        }}
        async function runQueryAlignment(filePayload) {{
          const formData = new FormData();
          formData.append('query_file', new File(
            [base64ToBytes(filePayload.data)],
            filePayload.name,
            {{ type: 'application/octet-stream' }}
          ));
          formData.append('tool', {tool!r});
          formData.append('extra_args', {alignment_args!r});
          formData.append('target_role', {target_role!r});
          const alignResponse = await apiFetch('/api/run_alignment', {{
            method: 'POST',
            body: formData
          }});
          if (!alignResponse.ok) {{
            throw new Error(await alignResponse.text());
          }}
          return alignResponse.json();
        }}
        const alignmentFile = {json.dumps(alignment_payload)};
        const queryFile = {json.dumps(query_payload)};
        if (alignmentFile || queryFile) {{
          const alignedPayload = alignmentFile
            ? await importAlignmentFile(alignmentFile)
            : await runQueryAlignment(queryFile);
          if (dom.colorMode) dom.colorMode.value = {color_mode!r};
          if (dom.alignmentShowBackground) dom.alignmentShowBackground.checked = true;
          renderGraph(alignedPayload, {{ relayout: false }});
          await new Promise((resolve) => setTimeout(resolve, 80));
        }}
        const svgText = buildGraphSvgExport({{ selectedOnly: false }});
        function bytesToBase64(bytes) {{
          let binary = '';
          const chunkSize = 0x8000;
          for (let index = 0; index < bytes.length; index += chunkSize) {{
            binary += String.fromCharCode.apply(null, bytes.subarray(index, index + chunkSize));
          }}
          return btoa(binary);
        }}
        const data = {svg_output}
          ? btoa(unescape(encodeURIComponent(svgText)))
          : bytesToBase64(buildPdfFromSvg(svgText));
        window.__gfaCliExportResult = {{ ok: true, data }};
      }} catch (error) {{
        window.__gfaCliExportResult = {{ ok: false, error: error?.message || String(error) }};
      }}
    }})();
    true;
    """
    window.evaluate_js(js)
    while time.time() < deadline:
        result = window.evaluate_js("window.__gfaCliExportResult")
        if isinstance(result, dict):
            if result.get("ok") and result.get("data"):
                return str(result["data"])
            raise RuntimeError(str(result.get("error") or "GUI export failed"))
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for GUI export")


def gui_colour_mode(colour: str) -> str:
    normalized = (colour or "depth").strip().lower().replace("_", "").replace("-", "")
    if normalized in {"blast", "blastsolid", "alignment", "alignments"}:
        return "alignment"
    if normalized == "readpath":
        return "read_path"
    if normalized in {"random", "degree"}:
        return normalized
    return "depth"


def file_payload(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise GuiRenderUnavailable(f"input file does not exist: {path}")
    return {
        "name": path.name,
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def gui_alignment_tool(tool: str) -> str:
    normalized = (tool or "auto").strip().lower()
    if normalized in {"blastn", "minimap2"}:
        return normalized
    if normalized == "auto":
        if shutil.which("blastn"):
            return "blastn"
        if shutil.which("minimap2"):
            return "minimap2"
    raise GuiRenderUnavailable("GUI alignment export requires --alignment-tool blastn/minimap2 or an installed auto tool")
