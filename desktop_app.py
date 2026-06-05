from __future__ import annotations

import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen
import webbrowser


def runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if sys.platform == "darwin" and executable.parent.name == "MacOS":
            return executable.parents[1] / "Resources"
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)  # type: ignore[attr-defined]
        internal = executable.parent / "_internal"
        return internal if internal.exists() else executable.parent
    return Path(__file__).resolve().parent


def platform_key() -> str:
    if sys.platform == "darwin":
        return "macos-arm64" if os.uname().machine == "arm64" else "macos-x86_64"
    if sys.platform.startswith("linux"):
        machine = os.uname().machine
        return "linux-arm64" if machine in {"aarch64", "arm64"} else "linux-x86_64"
    if sys.platform.startswith("win"):
        return "windows-x86_64"
    return f"{sys.platform}-{os.uname().machine if hasattr(os, 'uname') else 'unknown'}"


def prepend_bundled_tools(root: Path) -> None:
    candidates = [
        root / "packaging" / "bin" / platform_key(),
        root / "bin" / platform_key(),
        root / "bin",
    ]
    existing = [str(path) for path in candidates if path.exists()]
    if existing:
        os.environ["PATH"] = os.pathsep.join([*existing, os.environ.get("PATH", "")])


def prepend_import_roots(root: Path) -> None:
    for path in [root, root / "_internal"]:
        if path.exists():
            path_text = str(path)
            if path_text not in sys.path:
                sys.path.insert(0, path_text)


def find_available_port(preferred: int = 8000) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 50)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise RuntimeError("No available local port found.")


def wait_for_health(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(f"{url}/api/health", timeout=1).read()
            return True
        except (OSError, URLError):
            time.sleep(0.25)
    return False


def start_server(port: int):
    import uvicorn
    from backend.main import app as fastapi_app

    config = uvicorn.Config(
        fastapi_app,
        host="127.0.0.1",
        port=port,
        log_level=os.environ.get("GFA_EDITOR_LOG_LEVEL", "info"),
        reload=False,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="gfa-editor-server", daemon=True)
    thread.start()
    return server, thread


def run_embedded_webview(url: str, server) -> None:
    import webview

    window = webview.create_window("GFA Editor v1.0", url, width=1440, height=920, min_size=(1000, 680))

    def stop_server() -> None:
        server.should_exit = True

    window.events.closed += stop_server
    webview.start(debug=os.environ.get("GFA_EDITOR_DESKTOP_DEBUG", "0") == "1")


def open_default_browser(url: str) -> None:
    opened = webbrowser.open(url, new=2)
    if not opened and sys.platform == "darwin":
        subprocess.Popen(["open", url])


def keep_server_until_exit(server, thread: threading.Thread) -> None:
    def stop(_signum=None, _frame=None) -> None:
        server.should_exit = True

    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(signum, stop)
        except (ValueError, OSError):
            pass

    try:
        while thread.is_alive() and not server.should_exit:
            time.sleep(0.5)
    finally:
        server.should_exit = True
        thread.join(timeout=3)


def write_failure_log(exc: BaseException) -> None:
    log_dir = Path(os.environ.get("GFA_EDITOR_DATA_DIR", Path.home() / "GFAEditorData")).expanduser()
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        with (log_dir / "desktop.log").open("a", encoding="utf-8") as handle:
            handle.write("\n--- GFA Editor desktop failure ---\n")
            handle.write(traceback.format_exc())
    except Exception:
        print(f"Failed to write desktop failure log for: {exc}", file=sys.stderr)


def main() -> int:
    root = runtime_root()
    os.chdir(root)
    prepend_import_roots(root)
    os.environ["GFA_EDITOR_ROOT"] = str(root)
    os.environ["GFA_EDITOR_FRONTEND_DIR"] = str(root / "frontend")
    prepend_bundled_tools(root)

    data_dir = Path(os.environ.get("GFA_EDITOR_DATA_DIR", Path.home() / "GFAEditorData")).expanduser()
    data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["GFA_EDITOR_DATA_DIR"] = str(data_dir)

    preferred_port = int(os.environ.get("GFA_EDITOR_PORT", "8000"))
    port = find_available_port(preferred_port)
    url = f"http://127.0.0.1:{port}"
    server, thread = start_server(port)

    if not wait_for_health(url):
        server.should_exit = True
        thread.join(timeout=3)
        raise RuntimeError("The local GFA Editor server did not start.")

    mode = os.environ.get("GFA_EDITOR_DESKTOP_MODE", "auto").strip().lower()
    if mode not in {"auto", "webview", "browser"}:
        raise RuntimeError("GFA_EDITOR_DESKTOP_MODE must be one of: auto, webview, browser.")

    if mode in {"auto", "webview"}:
        try:
            run_embedded_webview(url, server)
            server.should_exit = True
            thread.join(timeout=3)
            return 0
        except Exception as exc:
            if mode == "webview":
                server.should_exit = True
                thread.join(timeout=3)
                raise
            print(f"Embedded webview failed, opening default browser instead: {exc}", file=sys.stderr)

    open_default_browser(url)
    keep_server_until_exit(server, thread)
    server.should_exit = True
    thread.join(timeout=3)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        write_failure_log(exc)
        print(f"GFA Editor desktop app failed: {exc}", file=sys.stderr)
        raise
