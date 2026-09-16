"""Bounded local USB-camera preview sessions with optional active-model inference."""

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Path as FastApiPath, Query, Request, Response
from pydantic import BaseModel, Field

from app import db, model_registry
from app.errors import AppError
from app.projects import WorkspaceDep, _read


router = APIRouter(prefix="/projects/{project_id}/cameras/usb", tags=["camera sessions"])
SessionStatus = Literal["starting", "running", "failed", "stopped"]
InferenceStatus = Literal["ready", "no_active_model", "unavailable"]


class CameraDetection(BaseModel):
    class_id: int = Field(ge=0)
    class_name: str
    confidence: float = Field(ge=0, le=1)
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(ge=0, le=1)
    height: float = Field(ge=0, le=1)


class CameraSessionResponse(BaseModel):
    id: str
    project_id: str
    camera_index: int
    status: SessionStatus
    inference_status: InferenceStatus
    active_model_id: str | None
    frame_id: int
    frame_width: int | None
    frame_height: int | None
    fps: float
    detections: list[CameraDetection]
    error: str | None


def _open_capture(index: int):
    import cv2

    backend = getattr(cv2, "CAP_DSHOW", None)
    return cv2.VideoCapture(index, backend) if backend is not None else cv2.VideoCapture(index)


def _encode_jpeg(frame) -> bytes | None:
    import cv2

    encoded, output = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return output.tobytes() if encoded else None


def _load_yolo(model_path: Path):
    from ultralytics import YOLO

    return YOLO(str(model_path))


def _as_list(value):
    return value.tolist() if hasattr(value, "tolist") else list(value)


def _infer(model, frame) -> list[CameraDetection]:
    height, width = frame.shape[:2]
    if not width or not height:
        return []
    results = model(frame, verbose=False, device="cpu")
    if not results:
        return []
    result = results[0]
    boxes = getattr(result, "boxes", None)
    if boxes is None:
        return []
    names = getattr(result, "names", {})
    detections: list[CameraDetection] = []
    for coordinates, confidence, class_id in zip(_as_list(boxes.xyxy), _as_list(boxes.conf), _as_list(boxes.cls)):
        x1, y1, x2, y2 = (float(value) for value in coordinates)
        numeric_class_id = int(class_id)
        class_name = names.get(numeric_class_id, str(numeric_class_id)) if isinstance(names, dict) else str(numeric_class_id)
        x = max(0.0, min(1.0, x1 / width))
        y = max(0.0, min(1.0, y1 / height))
        right = max(x, min(1.0, x2 / width))
        bottom = max(y, min(1.0, y2 / height))
        detections.append(CameraDetection(
            class_id=numeric_class_id, class_name=str(class_name),
            confidence=max(0.0, min(1.0, float(confidence))),
            x=x, y=y, width=right - x, height=bottom - y,
        ))
    return detections


@dataclass
class _CameraSession:
    id: str
    project_id: str
    camera_index: int
    active_model_id: str | None
    model_path: Path | None
    status: SessionStatus = "starting"
    inference_status: InferenceStatus = "no_active_model"
    error: str | None = None
    frame_id: int = 0
    frame_width: int | None = None
    frame_height: int | None = None
    fps: float = 0.0
    detections: list[CameraDetection] = field(default_factory=list)
    frame: bytes | None = None
    capture: object | None = None
    stop_event: threading.Event = field(default_factory=threading.Event)
    condition: threading.Condition = field(default_factory=threading.Condition)
    thread: threading.Thread | None = None

    def snapshot(self) -> CameraSessionResponse:
        with self.condition:
            return CameraSessionResponse(
                id=self.id, project_id=self.project_id, camera_index=self.camera_index,
                status=self.status, inference_status=self.inference_status,
                active_model_id=self.active_model_id, frame_id=self.frame_id,
                frame_width=self.frame_width, frame_height=self.frame_height, fps=self.fps,
                detections=self.detections, error=self.error,
            )

    def start(self) -> None:
        self.thread = threading.Thread(target=self._run, name=f"vision-camera-{self.id[:8]}", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        capture = self.capture
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass
        if self.thread is not None:
            self.thread.join(timeout=3)
        with self.condition:
            if self.status != "failed":
                self.status = "stopped"
            self.condition.notify_all()

    def wait_for_frame(self, after: int, timeout: float = 2.0) -> tuple[int, bytes] | None:
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.frame is None or self.frame_id <= after:
                if self.status in {"failed", "stopped"}:
                    return None
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self.condition.wait(remaining)
            return self.frame_id, self.frame

    def _fail(self, message: str) -> None:
        with self.condition:
            self.status = "failed"
            self.error = message
            self.condition.notify_all()

    def _run(self) -> None:
        capture = None
        try:
            try:
                capture = _open_capture(self.camera_index)
            except Exception:
                self._fail("The selected USB camera could not be opened.")
                return
            self.capture = capture
            if not capture.isOpened():
                self._fail("The selected USB camera could not be opened.")
                return
            model = None
            if self.model_path is not None:
                try:
                    model = _load_yolo(self.model_path)
                    self.inference_status = "ready"
                except Exception:
                    self.inference_status = "unavailable"
                    self._fail("The active model could not be loaded for camera inference.")
                    return
            started = time.monotonic()
            with self.condition:
                self.status = "running"
                self.condition.notify_all()
            while not self.stop_event.is_set():
                ok, image = capture.read()
                if not ok:
                    self._fail("The USB camera stopped delivering frames.")
                    return
                jpeg = _encode_jpeg(image)
                if jpeg is None:
                    self._fail("The USB camera frame could not be encoded.")
                    return
                detections = _infer(model, image) if model is not None else []
                elapsed = max(time.monotonic() - started, 0.001)
                with self.condition:
                    self.frame_id += 1
                    self.frame = jpeg
                    self.frame_height, self.frame_width = image.shape[:2]
                    self.fps = self.frame_id / elapsed
                    self.detections = detections
                    self.condition.notify_all()
        except Exception:
            self._fail("The local camera session stopped unexpectedly. Check the application logs and try again.")
        finally:
            if capture is not None:
                try:
                    capture.release()
                except Exception:
                    pass
            self.capture = None
            with self.condition:
                if self.status != "failed":
                    self.status = "stopped"
                self.condition.notify_all()


class CameraSessionManager:
    def __init__(self, data_root: Path, database: Path):
        self.data_root = data_root
        self.database = database
        self._sessions: dict[str, _CameraSession] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str, camera_index: int) -> _CameraSession:
        with db.session(self.database) as connection:
            project = _read(connection, project_id)
            active_model_id = project["active_model_id"]
            model_path = None
            if active_model_id is not None:
                model = model_registry._read_model(connection, project_id, active_model_id)
                if model["status"] == "archived":
                    raise AppError(409, "active_model_archived", "The active model is archived. Choose another production model before starting inference.")
                model_path = model_registry._model_path(self.data_root, project_id, model["relative_path"])
                if not model_path.is_file():
                    raise AppError(409, "model_artifact_missing", "The active model checkpoint is missing. Choose another production model before starting inference.")
        session = _CameraSession(uuid.uuid4().hex, project_id, camera_index, active_model_id, model_path)
        with self._lock:
            self._sessions[session.id] = session
        session.start()
        return session

    def get(self, project_id: str, session_id: str) -> _CameraSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if session is None or session.project_id != project_id:
            raise AppError(404, "camera_session_not_found", "The local camera session is no longer available.")
        return session

    def stop(self, project_id: str, session_id: str) -> None:
        session = self.get(project_id, session_id)
        session.stop()
        with self._lock:
            self._sessions.pop(session_id, None)

    def shutdown(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.stop()


def _manager(request: Request) -> CameraSessionManager:
    return request.app.state.camera_sessions


SessionDep = Depends(_manager)


@router.post("/{camera_index}/sessions", response_model=CameraSessionResponse, status_code=201)
def start_camera_session(project_id: str, camera_index: int = FastApiPath(ge=0, le=9), manager: CameraSessionManager = SessionDep) -> CameraSessionResponse:
    return manager.start(project_id, camera_index).snapshot()


@router.get("/sessions/{session_id}", response_model=CameraSessionResponse)
def read_camera_session(project_id: str, session_id: str, manager: CameraSessionManager = SessionDep) -> CameraSessionResponse:
    return manager.get(project_id, session_id).snapshot()


@router.get("/sessions/{session_id}/frame")
def read_camera_frame(project_id: str, session_id: str, after: int = Query(default=0, ge=0), manager: CameraSessionManager = SessionDep):
    session = manager.get(project_id, session_id)
    frame = session.wait_for_frame(after)
    if frame is None:
        snapshot = session.snapshot()
        if snapshot.status == "failed":
            raise AppError(409, "camera_session_failed", snapshot.error or "The local camera session failed.")
        return Response(status_code=204)
    frame_id, jpeg = frame
    snapshot = session.snapshot()
    return Response(
        content=jpeg,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "no-store",
            "X-Vision-Frame-Id": str(frame_id),
            "X-Vision-Detections": json.dumps([item.model_dump() for item in snapshot.detections], separators=(",", ":")),
        },
    )


@router.delete("/sessions/{session_id}", status_code=204)
def stop_camera_session(project_id: str, session_id: str, manager: CameraSessionManager = SessionDep) -> Response:
    manager.stop(project_id, session_id)
    return Response(status_code=204)
