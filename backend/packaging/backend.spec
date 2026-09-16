# Build on Windows x64 with the repository's locked build environment.
from pathlib import Path
import sys

from PyInstaller.utils.hooks import get_package_paths

backend_root = Path(SPECPATH).parent
repo_root = backend_root.parent
sys.path.insert(0, str(backend_root))
from app import base_models

torchvision_root = Path(get_package_paths("torchvision")[1])
base_model_root = repo_root / "backend" / "assets" / "models"
base_model_asset = base_model_root / "yolo11n.pt"
if not base_models.is_valid_model(base_model_asset):
    raise SystemExit("The Phase 16 yolo11n.pt base model must pass its integrity check before packaging.")

# Torchvision 0.29 loads _C_stable.pyd through torch.ops.load_library(), so
# PyInstaller cannot infer it from an ordinary Python import. Preserve all
# native torchvision extensions at their package-relative paths.
torchvision_extensions = [
    (str(path), str(path.parent.relative_to(torchvision_root.parent)))
    for path in torchvision_root.rglob("*.pyd")
]
base_model_assets = [
    (str(path), str(path.parent.relative_to(repo_root / "backend")))
    for path in base_model_root.rglob("*")
    if path.is_file()
]

a = Analysis(
    [str(backend_root / "run_backend.py")],
    pathex=[str(backend_root)],
    binaries=torchvision_extensions,
    datas=base_model_assets,
    hiddenimports=[
        "app.main",
        "app.model_registry",
        "app.cameras",
        "app.camera_sessions",
        "app.training_worker",
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
    excludes=["pytest", "httpx", "httpcore", "pip"],
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
