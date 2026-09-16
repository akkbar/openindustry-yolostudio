"""Bounded local USB-camera preview sessions with optional active-model inference."""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, Field

from app import cameras, counting, db, events, model_catalog, model_registry, project_cameras
from app.errors import AppError
from app.projects import WorkspaceDep, _read


router = APIRouter(prefix="/projects/{project_id}/cameras/usb", tags=["camera sessions"])
rtsp_router = APIRouter(prefix="/projects/{project_id}/cameras/rtsp", tags=["camera sessions"])
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
    track_id: int | None = Field(default=None, ge=1)


class CameraCounter(BaseModel):
    line_id: str
    line_name: str
    count: int = Field(ge=0)
    a_to_b: int = Field(ge=0)
    b_to_a: int = Field(ge=0)


class UsbCameraStartRequest(BaseModel):
    index: int = Field(ge=0, le=9)
    name: str = Field(min_length=1, max_length=160)


class CameraSessionResponse(BaseModel):
    id: str
    project_id: str
    camera_index: int | None
    camera_id: str | None
    camera_name: str
    source_type: Literal["usb", "rtsp"]
    reconnect_count: int = Field(ge=0)
    video_status: Literal["receiving", "black_frames"]
    status: SessionStatus
    inference_status: InferenceStatus
    active_model_id: str | None
    active_model_source: Literal["custom", "catalog", "none"]
    active_catalog_model_id: str | None
    recommended_confidence: float
    roi_active: bool
    counters: list[CameraCounter]
    frame_id: int
    frame_width: int | None
    frame_height: int | None
    fps: float
    detections: list[CameraDetection]
    error: str | None


def _open_capture(index: int):
    return cameras._open_capture(index)


def _open_rtsp_capture(url: str):
    import cv2
    return cv2.VideoCapture(url)


def _encode_jpeg(frame) -> bytes | None:
    import cv2

    encoded, output = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return output.tobytes() if encoded else None


def _load_yolo(model_path: Path):
    from ultralytics import YOLO

    return YOLO(str(model_path))


def _as_list(value):
    return value.tolist() if hasattr(value, "tolist") else list(value)


def _infer(model, frame, class_filter: tuple[str, ...] = ()) -> list[CameraDetection]:
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
        if class_filter and str(class_name).casefold() not in {name.casefold() for name in class_filter}:
            continue
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
    camera_index: int | None
    active_model_id: str | None
    model_path: Path | None
    active_model_source: Literal["custom", "catalog", "none"] = "none"
    active_catalog_model_id: str | None = None
    class_filter: tuple[str, ...] = ()
    recommended_confidence: float = 0.5
    camera_id: str | None = None
    camera_name: str = "USB camera"
    source_type: Literal["usb", "rtsp"] = "usb"
    source_url: str | None = None
    reconnect_count: int = 0
    video_status: Literal["receiving", "black_frames"] = "receiving"
    black_frame_count: int = 0
    data_root: Path = field(default_factory=Path)
    database: Path = field(default_factory=Path)
    roi: counting.RoiConfig | None = None
    tracker: counting.ByteTrackTracker = field(default_factory=counting.ByteTrackTracker)
    counter: counting.CrossingCounter = field(default_factory=counting.CrossingCounter)
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
                camera_id=self.camera_id, camera_name=self.camera_name, source_type=self.source_type, reconnect_count=self.reconnect_count, video_status=self.video_status,
                status=self.status, inference_status=self.inference_status,
                active_model_id=self.active_model_id, frame_id=self.frame_id,
                active_model_source=self.active_model_source, active_catalog_model_id=self.active_catalog_model_id,
                recommended_confidence=self.recommended_confidence,
                roi_active=self.roi is not None and self.roi.enabled,
                counters=[CameraCounter.model_validate(item) for item in self.counter.snapshot()],
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

    def _connect(self):
        if self.source_type == "rtsp":
            return _open_rtsp_capture(self.source_url or "")
        return _open_capture(self.camera_index)

    def _wait_to_reconnect(self) -> bool:
        self.reconnect_count += 1
        with self.condition:
            self.error = "The RTSP camera connection was interrupted. Reconnecting."
            self.condition.notify_all()
        return not self.stop_event.wait(min(5.0, 0.25 * self.reconnect_count))

    def _run(self) -> None:
        capture = None
        first_frame_deadline = 0.0
        try:
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
            while not self.stop_event.is_set():
                if capture is None:
                    try:
                        candidate = self._connect()
                    except Exception:
                        candidate = None
                    if candidate is None or not candidate.isOpened():
                        if candidate is not None:
                            try:
                                candidate.release()
                            except Exception:
                                pass
                        if self.source_type == "usb":
                            self._fail("The selected USB camera could not be opened.")
                            return
                        if not self._wait_to_reconnect():
                            return
                        continue
                    capture = candidate
                    self.capture = capture
                    first_frame_deadline = time.monotonic() + 3.0
                    with self.condition:
                        self.status = "running"
                        self.error = None
                        self.condition.notify_all()
                ok, image = capture.read()
                if not ok:
                    if self.source_type == "usb":
                        self._fail("The USB camera stopped delivering frames.")
                        return
                    try:
                        capture.release()
                    except Exception:
                        pass
                    capture = None
                    self.capture = None
                    if not self._wait_to_reconnect():
                        return
                    continue
                jpeg = _encode_jpeg(image)
                if jpeg is None:
                    self._fail("The USB camera frame could not be encoded.")
                    return
                # Several UVC cameras, including common webcam drivers, report a
                # successful open while their first frames are still all black.
                # Keep the preview in its loading state until a usable frame
                # arrives, or expose a persistent black stream after three seconds.
                if self.frame_id == 0 and float(image.mean()) <= 2.0 and time.monotonic() < first_frame_deadline:
                    continue
                detections = _infer(model, image, self.class_filter) if model is not None else []
                detections = counting.filter_roi(detections, self.roi)
                observations = self.tracker.update(detections)
                for observation in observations:
                    observation.detection.track_id = observation.track_id
                crossings = self.counter.observe(observations)
                for crossing in crossings:
                    try:
                        events.record_line_cross(
                            self.database, self.data_root, self.project_id, self.camera_id,
                            crossing.observation.detection.class_name, crossing.observation.track_id,
                            crossing.observation.detection.confidence, crossing.count, jpeg,
                        )
                    except Exception:
                        logging.exception("Could not persist camera line-cross event.")
                elapsed = max(time.monotonic() - started, 0.001)
                with self.condition:
                    if float(image.mean()) <= 2.0:
                        self.black_frame_count += 1
                    else:
                        self.black_frame_count = 0
                    self.video_status = "black_frames" if self.black_frame_count >= 30 else "receiving"
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

    def start(self, project_id: str, camera_index: int | None, *, camera_id: str | None = None, camera_name: str | None = None, source_type: Literal["usb", "rtsp"] = "usb", source_url: str | None = None) -> _CameraSession:
        with db.session(self.database) as connection:
            project = _read(connection, project_id)
            active_model_id = project["active_model_id"]
            model_path = None
            active_model_source: Literal["custom", "catalog", "none"] = "none"
            active_catalog_model_id = None
            class_filter: tuple[str, ...] = ()
            recommended_confidence = 0.5
            selection = model_catalog.selected_project_model(connection, project_id)
            if selection is not None:
                catalog_definition, settings = selection
                model_path, class_filter, recommended_confidence = model_catalog.runtime_model(connection, self.data_root, catalog_definition.id)
                active_model_source = "catalog"
                active_catalog_model_id = catalog_definition.id
                active_model_id = f"catalog:{catalog_definition.id}"
                confidence = settings.get("confidence")
                if isinstance(confidence, (float, int)) and 0.01 <= confidence <= 1:
                    recommended_confidence = float(confidence)
            elif active_model_id is not None:
                model = model_registry._read_model(connection, project_id, active_model_id)
                if model["status"] == "archived":
                    raise AppError(409, "active_model_archived", "The active model is archived. Choose another production model before starting inference.")
                model_path = model_registry._model_path(self.data_root, project_id, model["relative_path"])
                if not model_path.is_file():
                    raise AppError(409, "model_artifact_missing", "The active model checkpoint is missing. Choose another production model before starting inference.")
                active_model_source = "custom"
            counting_config = counting.configuration(connection, project_id)
        session = _CameraSession(
            uuid.uuid4().hex, project_id, camera_index, active_model_id, model_path,
            active_model_source, active_catalog_model_id, class_filter, recommended_confidence,
            camera_id=camera_id, camera_name=camera_name or (f"Camera {camera_index}" if camera_index is not None else "RTSP camera"), source_type=source_type, source_url=source_url, data_root=self.data_root, database=self.database,
            roi=counting_config.roi, counter=counting.CrossingCounter(counting_config.lines),
        )
        with self._lock:
            self._sessions[session.id] = session
        session.start()
        return session

    def start_rtsp(self, project_id: str, camera_id: str) -> _CameraSession:
        with db.session(self.database) as connection:
            _read(connection, project_id)
            camera = project_cameras.read_rtsp_camera(connection, project_id, camera_id)
            source_url = _rtsp_url(camera["url"], camera["username"], camera["password"])
            camera_name = camera["name"]
        return self.start(project_id, None, camera_id=camera_id, camera_name=camera_name, source_type="rtsp", source_url=source_url)

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

    def reload_counting(self, project_id: str, session_id: str) -> _CameraSession:
        session = self.get(project_id, session_id)
        with db.session(self.database) as connection:
            config = counting.configuration(connection, project_id)
        with session.condition:
            session.roi = config.roi
            session.tracker = counting.ByteTrackTracker()
            session.counter = counting.CrossingCounter(config.lines)
            session.detections = []
        return session

    def shutdown(self) -> None:
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            session.stop()


def _manager(request: Request) -> CameraSessionManager:
    return request.app.state.camera_sessions


SessionDep = Depends(_manager)


@router.post("/{camera_id}/sessions", response_model=CameraSessionResponse, status_code=201)
def start_camera_session(project_id: str, camera_id: str, payload: UsbCameraStartRequest | None = None, manager: CameraSessionManager = SessionDep) -> CameraSessionResponse:
    if payload is None:
        # Preserve the former numeric endpoint for local clients during upgrade.
        try:
            camera_index = int(camera_id)
        except ValueError as error:
            raise AppError(422, "usb_camera_selection_invalid", "Rescan USB cameras and select a camera by name.") from error
        if not 0 <= camera_index <= 9:
            raise AppError(422, "usb_camera_selection_invalid", "Rescan USB cameras and select a camera by name.")
        return manager.start(project_id, camera_index, camera_id=f"usb-{camera_index}", camera_name=f"USB camera {camera_index + 1}").snapshot()
    return manager.start(project_id, payload.index, camera_id=camera_id, camera_name=payload.name).snapshot()


def _rtsp_url(url: str, username: str | None, password: str | None) -> str:
    if not username:
        return url
    from urllib.parse import quote, urlsplit, urlunsplit
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"
    credentials = quote(username, safe="")
    if password:
        credentials = f"{credentials}:{quote(password, safe='')}"
    return urlunsplit((parsed.scheme, f"{credentials}@{host}", parsed.path, parsed.query, parsed.fragment))


@rtsp_router.post("/{camera_id}/sessions", response_model=CameraSessionResponse, status_code=201)
def start_rtsp_camera_session(project_id: str, camera_id: str, manager: CameraSessionManager = SessionDep) -> CameraSessionResponse:
    return manager.start_rtsp(project_id, camera_id).snapshot()


@router.get("/sessions/{session_id}", response_model=CameraSessionResponse)
@rtsp_router.get("/sessions/{session_id}", response_model=CameraSessionResponse)
def read_camera_session(project_id: str, session_id: str, manager: CameraSessionManager = SessionDep) -> CameraSessionResponse:
    return manager.get(project_id, session_id).snapshot()


@router.post("/sessions/{session_id}/counting/reload", response_model=CameraSessionResponse)
@rtsp_router.post("/sessions/{session_id}/counting/reload", response_model=CameraSessionResponse)
def reload_camera_counting(project_id: str, session_id: str, manager: CameraSessionManager = SessionDep) -> CameraSessionResponse:
    return manager.reload_counting(project_id, session_id).snapshot()


@router.get("/sessions/{session_id}/frame")
@rtsp_router.get("/sessions/{session_id}/frame")
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
            "X-Vision-Counters": json.dumps([item.model_dump() for item in snapshot.counters], separators=(",", ":")),
            "X-Vision-ROI-Active": "true" if snapshot.roi_active else "false",
        },
    )


@router.delete("/sessions/{session_id}", status_code=204)
@rtsp_router.delete("/sessions/{session_id}", status_code=204)
def stop_camera_session(project_id: str, session_id: str, manager: CameraSessionManager = SessionDep) -> Response:
    manager.stop(project_id, session_id)
    return Response(status_code=204)
