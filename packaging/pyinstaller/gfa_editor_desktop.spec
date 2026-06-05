# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import sys

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).resolve().parents[1]
mac_icon = project_root / "packaging" / "icons" / "GFA_Editor.icns"
win_icon = project_root / "packaging" / "icons" / "GFA_Editor.ico"
exe_icon = str(win_icon) if sys.platform == "win32" and win_icon.exists() else None
bundle_icon = str(mac_icon) if mac_icon.exists() else None

datas = [
    (str(project_root / "frontend"), "frontend"),
    (str(project_root / "examples"), "examples"),
]

bin_root = project_root / "packaging" / "bin"
if bin_root.exists():
    datas.append((str(bin_root), "packaging/bin"))

hiddenimports = [
    *collect_submodules("backend"),
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.loops.auto",
]

a = Analysis(
    [str(project_root / "desktop_app.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    name="GFA_Editor",
    debug=False,
    bootloader_ignore_signals=False,
    exclude_binaries=True,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon=exe_icon,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GFA_Editor",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="GFA_Editor.app",
        icon=bundle_icon,
        bundle_identifier="local.gfa-editor",
        info_plist={
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
        },
    )
