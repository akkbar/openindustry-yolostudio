# Build on Windows x64 with the repository's locked build environment.
from pathlib import Path

backend_root = Path(SPECPATH).parent
repo_root = backend_root.parent

a = Analysis(
    [str(backend_root / "run_backend.py")],
    pathex=[str(backend_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "app.main",
        # Declared explicitly because it carries a binary extension and a DLL.
        "sqlite3",
        "uvicorn.logging",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.lifespan.on",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["pytest", "httpx", "httpcore", "pip", "torch", "ultralytics", "cv2"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    icon=str(repo_root / "desktop" / "icons" / "icon.ico"),
    contents_directory="_internal",
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="backend")
