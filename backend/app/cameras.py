"""On-demand USB-camera discovery with Windows device friendly names."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel


router = APIRouter(prefix="/cameras", tags=["cameras"])
_scan_lock = Lock()


class UsbCameraResponse(BaseModel):
    id: str
    index: int
    name: str
    source_type: Literal["usb"] = "usb"


class UsbCameraListResponse(BaseModel):
    cameras: list[UsbCameraResponse]
    scanned: int


def _open_capture(index: int):
    import cv2

    backends = (getattr(cv2, "CAP_DSHOW", None), getattr(cv2, "CAP_MSMF", None), cv2.CAP_ANY)
    attempted: set[int] = set()
    for backend in backends:
        if backend is None or backend in attempted:
            continue
        attempted.add(backend)
        capture = cv2.VideoCapture(index, backend)
        if capture.isOpened():
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            return capture
        capture.release()
    return cv2.VideoCapture(index)


def _windows_devices() -> list[tuple[str, str]]:
    """Read present camera friendly names without an extra Python package."""
    if os.name != "nt":
        return []
    command = (
        "$ErrorActionPreference='Stop'; Get-CimInstance Win32_PnPEntity | "
        "Where-Object { $_.Present -and ($_.PNPClass -eq 'Camera' -or $_.PNPClass -eq 'Image') } | "
        "Select-Object Name,DeviceID | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            check=True, capture_output=True, text=True, timeout=4,
        )
        raw = completed.stdout.strip()
        if not raw:
            return []
        items = json.loads(raw)
        if isinstance(items, dict):
            items = [items]
        return [(str(item["Name"]), str(item["DeviceID"])) for item in items if item.get("Name") and item.get("DeviceID")]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        return []


def _camera_id(device_id: str, index: int) -> str:
    digest = hashlib.sha256(f"{device_id}\0{index}".encode()).hexdigest()[:16]
    return f"usb-{digest}"


def scan_usb_cameras(limit: int) -> list[UsbCameraResponse]:
    opened_indexes: list[int] = []
    # DirectShow camera drivers are not generally safe to probe concurrently.
    with _scan_lock:
        for index in range(limit):
            capture = _open_capture(index)
            try:
                if capture.isOpened():
                    opened_indexes.append(index)
            finally:
                capture.release()
    devices = _windows_devices()
    cameras: list[UsbCameraResponse] = []
    for position, index in enumerate(opened_indexes):
        if position < len(devices):
            name, device_id = devices[position]
        else:
            name, device_id = f"USB camera {index + 1}", f"opencv-index-{index}"
        cameras.append(UsbCameraResponse(id=_camera_id(device_id, index), index=index, name=name))
    return cameras


@router.get("/usb", response_model=UsbCameraListResponse)
def list_usb_cameras(limit: int = Query(default=4, ge=1, le=10)) -> UsbCameraListResponse:
    return UsbCameraListResponse(cameras=scan_usb_cameras(limit), scanned=limit)
