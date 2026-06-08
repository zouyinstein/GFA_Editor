from __future__ import annotations

import argparse
import os
from pathlib import Path
import platform
import shutil
import stat


def platform_key() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "darwin":
        return "macos-arm64" if machine in {"arm64", "aarch64"} else "macos-x86_64"
    if system == "linux":
        return "linux-arm64" if machine in {"arm64", "aarch64"} else "linux-x86_64"
    if system == "windows":
        return "windows-x86_64"
    return f"{system}-{machine}"


def copy_tool(tool: str, dest_dir: Path) -> None:
    tool_path = shutil.which(tool) or shutil.which(f"{tool}.exe")
    if tool_path is None:
        print(f"Missing {tool} on PATH; skipped.")
        return

    source = Path(tool_path)
    dest_name = f"{tool}.exe" if os.name == "nt" and not tool.endswith(".exe") else tool
    dest = dest_dir / dest_name
    if dest.exists():
        dest.chmod(dest.stat().st_mode | stat.S_IWRITE)
        dest.unlink()
    shutil.copy2(source, dest)
    dest.chmod(dest.stat().st_mode | stat.S_IEXEC | stat.S_IREAD)
    print(f"Copied {tool} -> {dest}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy minimap2/blastn into packaging/bin/<platform>.")
    parser.add_argument(
        "dest_root",
        nargs="?",
        default=str(Path(__file__).resolve().parents[1] / "packaging" / "bin"),
    )
    args = parser.parse_args()

    dest_dir = Path(args.dest_root) / platform_key()
    dest_dir.mkdir(parents=True, exist_ok=True)
    copy_tool("minimap2", dest_dir)
    copy_tool("blastn", dest_dir)
    print()
    print("Note:")
    print("  minimap2 is usually a single executable.")
    print("  blastn may depend on shared libraries from the BLAST installation.")
    print("  Test the packaged app on a clean machine before sharing it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
