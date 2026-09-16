"""Initialize the bundled CPU YOLO runtime without downloading model weights."""

import logging
import os
from pathlib import Path
from typing import Literal, TypedDict


class VisionRuntimeInfo(TypedDict):
    status: Literal["ready"]
    ultralytics_version: str
    torch_version: str
    torchvision_version: str
    opencv_version: str


_runtime_info: VisionRuntimeInfo | None = None


def initialize_runtime(data_root: Path) -> VisionRuntimeInfo:
    """Import and configure the runtime once for the lifetime of this backend."""
    global _runtime_info
    if _runtime_info is not None:
        return _runtime_info

    runtime_root = data_root / "vision-runtime"
    matplotlib_root = runtime_root / "matplotlib"
    runtime_root.mkdir(parents=True, exist_ok=True)
    matplotlib_root.mkdir(parents=True, exist_ok=True)

    # These libraries otherwise use the roaming profile or the current working
    # directory, neither of which is suitable for a packaged desktop app.
    os.environ["YOLO_CONFIG_DIR"] = str(runtime_root)
    os.environ["YOLO_AUTOINSTALL"] = "False"
    os.environ["MPLCONFIGDIR"] = str(matplotlib_root)
    os.environ["MPLBACKEND"] = "Agg"

    try:
        import cv2
        import torch
        import torchvision
        import ultralytics
        from ultralytics import YOLO, settings

        if not callable(YOLO):
            raise RuntimeError("Ultralytics did not provide a usable YOLO class.")
        settings.update(
            {
                "datasets_dir": str(data_root / "datasets"),
                "weights_dir": str(data_root / "models"),
                "runs_dir": str(data_root / "runs"),
                "sync": False,
                "vscode_msg": False,
            }
        )
    except Exception as error:
        logging.exception("The YOLO runtime could not be initialized.")
        raise RuntimeError(
            "The YOLO runtime could not be initialized. Reinstall Vision Studio and try again."
        ) from error

    _runtime_info = {
        "status": "ready",
        "ultralytics_version": ultralytics.__version__,
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "opencv_version": cv2.__version__,
    }
    logging.info(
        "YOLO runtime is ready: Ultralytics %s, PyTorch %s, Torchvision %s, OpenCV %s.",
        _runtime_info["ultralytics_version"],
        _runtime_info["torch_version"],
        _runtime_info["torchvision_version"],
        _runtime_info["opencv_version"],
    )
    return _runtime_info
