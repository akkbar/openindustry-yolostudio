"""Writable application storage, independent of the working directory."""

import os
from pathlib import Path

from platformdirs import user_data_path


def data_root() -> Path:
    override = os.getenv("VISION_STUDIO_DATA_DIR")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute():
            raise ValueError("VISION_STUDIO_DATA_DIR must be an absolute path.")
        return path
    return user_data_path("VisionStudio", appauthor=False, roaming=False)


def initialize_storage() -> Path:
    root = data_root()
    for directory in ("data", "projects", "logs", "demo-datasets"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    return root
