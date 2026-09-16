"""On-demand USB camera discovery; preview streaming belongs to Phase 23."""

from typing import Literal
from threading import Lock

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

    backend = getattr(cv2, "CAP_DSHOW", None)
    return cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)


def scan_usb_cameras(limit: int) -> list[UsbCameraResponse]:
    cameras: list[UsbCameraResponse] = []
    # DirectShow camera drivers are not generally safe to probe concurrently.
    # Strict-mode page mounts and rapid refreshes can otherwise open the same
    # hardware index from separate request threads at once.
    with _scan_lock:
        for index in range(limit):
            capture = _open_capture(index)
            try:
                if capture.isOpened():
                    cameras.append(UsbCameraResponse(id=f"usb-{index}", index=index, name=f"Camera {index}"))
            finally:
                capture.release()
    return cameras


@router.get("/usb", response_model=UsbCameraListResponse)
def list_usb_cameras(limit: int = Query(default=4, ge=1, le=10)) -> UsbCameraListResponse:
    return UsbCameraListResponse(cameras=scan_usb_cameras(limit), scanned=limit)
