"""Provision the immutable Phase 16 base model into writable application data."""

import hashlib
import logging
import os
import shutil
import sys
import threading
from pathlib import Path
from typing import Literal, TypedDict
from uuid import uuid4


MODEL_ID = "yolo11n"
MODEL_NAME = "YOLO11 Nano"
MODEL_TASK = "object_detection"
MODEL_FILE_NAME = "yolo11n.pt"
MODEL_BYTES = 5_613_764
MODEL_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
MODEL_SOURCE_URL = "https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt"
MODEL_LICENSE = "AGPL-3.0 or Enterprise"


class BaseModelInfo(TypedDict):
    status: Literal["ready"]
    id: Literal["yolo11n"]
    display_name: Literal["YOLO11 Nano"]
    task: Literal["object_detection"]
    file_name: Literal["yolo11n.pt"]
    path: str
    byte_size: int
    sha256: str
    distribution: Literal["bundled"]
    load_verified: bool
    license: str


_load_lock = threading.Lock()
_source_load_verified = False


def assets_root() -> Path:
    """Return the immutable asset directory for source and frozen execution."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "assets"  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1] / "assets"


def bundled_model_path() -> Path:
    return assets_root() / "models" / MODEL_FILE_NAME


def model_path(data_root: Path) -> Path:
    """Resolve the one allowed writable location for the bundled base model."""
    models_root = data_root / "models"
    models_root.mkdir(parents=True, exist_ok=True)
    base_root = models_root / "base"
    base_root.mkdir(parents=True, exist_ok=True)

    resolved_models_root = models_root.resolve()
    resolved_base_root = base_root.resolve()
    try:
        resolved_base_root.relative_to(resolved_models_root)
    except ValueError as error:
        raise RuntimeError("The base-model storage directory is outside application data.") from error

    target = base_root / MODEL_FILE_NAME
    if target.resolve().parent != resolved_base_root:
        raise RuntimeError("The base-model path is outside application data.")
    return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_valid_model(path: Path) -> bool:
    return path.is_file() and path.stat().st_size == MODEL_BYTES and _sha256(path) == MODEL_SHA256


def _require_valid_model(path: Path, location: str) -> None:
    if not path.is_file():
        raise RuntimeError(f"The {location} base model is missing.")
    if path.stat().st_size != MODEL_BYTES or _sha256(path) != MODEL_SHA256:
        raise RuntimeError(f"The {location} base model did not pass its integrity check.")


def _verify_bundled_model_load(source: Path) -> None:
    """Deserialize the exact bundled checkpoint once without any network fallback."""
    global _source_load_verified
    if _source_load_verified:
        return

    with _load_lock:
        if _source_load_verified:
            return
        try:
            from ultralytics import YOLO

            loaded = YOLO(str(source))
            if loaded.task != "detect":
                raise RuntimeError(f"The bundled model task is {loaded.task!r}, not object detection.")
        except Exception as error:
            logging.exception("The bundled base model could not be loaded.")
            raise RuntimeError(
                "The bundled base model could not be loaded for offline training. "
                "Reinstall Vision Studio and try again."
            ) from error
        _source_load_verified = True


def _copy_atomically(source: Path, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    try:
        with source.open("rb") as input_file, temporary.open("xb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
        _require_valid_model(temporary, "staged")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()


def provision_base_model(data_root: Path) -> BaseModelInfo:
    """Verify the packaged checkpoint and make an identical local copy available."""
    source = bundled_model_path()
    _require_valid_model(source, "bundled")
    _verify_bundled_model_load(source)

    destination = model_path(data_root)
    if not is_valid_model(destination):
        _copy_atomically(source, destination)
    _require_valid_model(destination, "provisioned")

    logging.info("Bundled base model is ready for offline training at %s.", destination)
    return {
        "status": "ready",
        "id": MODEL_ID,
        "display_name": MODEL_NAME,
        "task": MODEL_TASK,
        "file_name": MODEL_FILE_NAME,
        "path": str(destination),
        "byte_size": MODEL_BYTES,
        "sha256": MODEL_SHA256,
        "distribution": "bundled",
        "load_verified": True,
        "license": MODEL_LICENSE,
    }
