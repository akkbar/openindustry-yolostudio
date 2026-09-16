import json
import time
import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import camera_sessions, db
from app.main import app
from app.projects import _now


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        yield client, root


def create_project(client):
    response = client.post("/projects", json={"name": "Camera session"})
    assert response.status_code == 201
    return response.json()["id"]


class Capture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        time.sleep(0.01)
        return (False, None) if self.released else (True, np.full((40, 80, 3), 127, dtype=np.uint8))

    def release(self):
        self.released = True


def wait_for_frame(client, project_id, session_id):
    for _ in range(30):
        response = client.get(f"/projects/{project_id}/cameras/usb/sessions/{session_id}/frame")
        if response.status_code == 200:
            return response
        time.sleep(0.03)
    raise AssertionError("The camera session did not produce a JPEG frame.")


def test_preview_session_returns_jpeg_and_releases_camera_on_stop(workspace, monkeypatch):
    client, _ = workspace
    project_id = create_project(client)
    capture = Capture()
    monkeypatch.setattr(camera_sessions, "_open_capture", lambda _: capture)

    started = client.post(f"/projects/{project_id}/cameras/usb/usb-receiving/sessions", json={"index": 0, "name": "Receiving camera"})
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    frame = wait_for_frame(client, project_id, session_id)
    assert frame.headers["content-type"] == "image/jpeg"
    assert frame.headers["x-vision-frame-id"] == "1"
    assert json.loads(frame.headers["x-vision-detections"]) == []
    state = client.get(f"/projects/{project_id}/cameras/usb/sessions/{session_id}").json()
    assert state["status"] == "running"
    assert state["camera_id"] == "usb-receiving" and state["camera_name"] == "Receiving camera"
    assert state["inference_status"] == "no_active_model"
    assert state["frame_width"] == 80 and state["frame_height"] == 40

    assert client.delete(f"/projects/{project_id}/cameras/usb/sessions/{session_id}").status_code == 204
    assert capture.released is True
    assert client.get(f"/projects/{project_id}/cameras/usb/sessions/{session_id}").status_code == 404


def test_active_model_inference_returns_normalized_live_detections(workspace, monkeypatch):
    client, root = workspace
    project_id = create_project(client)
    model_id = uuid.uuid4().hex
    model_path = root / "projects" / project_id / "models" / f"{model_id}.pt"
    model_path.write_bytes(b"model")
    with db.transaction(db.database_path(root)) as connection:
        connection.execute(
            "INSERT INTO models (id, project_id, name, version, status, relative_path, metrics, created_at, settings) VALUES (?, ?, ?, 1, 'production', ?, '{}', ?, '{}')",
            (model_id, project_id, "banana-v1", f"models/{model_id}.pt", _now()),
        )
        connection.execute("UPDATE projects SET active_model_id = ? WHERE id = ?", (model_id, project_id))

    class Values:
        def __init__(self, value): self.value = value
        def tolist(self): return self.value

    class Boxes:
        xyxy = Values([[8, 4, 48, 24]])
        conf = Values([0.8])
        cls = Values([0])

    class Result:
        boxes = Boxes()
        names = {0: "Banana"}

    monkeypatch.setattr(camera_sessions, "_load_yolo", lambda _: lambda *_args, **_kwargs: [Result()])
    capture = Capture()
    monkeypatch.setattr(camera_sessions, "_open_capture", lambda _: capture)

    started = client.post(f"/projects/{project_id}/cameras/usb/0/sessions")
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    frame = wait_for_frame(client, project_id, session_id)
    assert json.loads(frame.headers["x-vision-detections"]) == [{
        "class_id": 0, "class_name": "Banana", "confidence": 0.8,
        "x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5, "track_id": 1,
    }]
    state = client.get(f"/projects/{project_id}/cameras/usb/sessions/{session_id}").json()
    assert state["inference_status"] == "ready" and state["active_model_id"] == model_id
    assert client.delete(f"/projects/{project_id}/cameras/usb/sessions/{session_id}").status_code == 204
