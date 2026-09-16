import time

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import camera_sessions
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(tmp_path / "VisionStudio"))
    with TestClient(app) as test_client:
        yield test_client


class _DroppedCapture:
    def isOpened(self):
        return True

    def read(self):
        return False, None

    def release(self):
        pass


class _Capture:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def read(self):
        time.sleep(0.01)
        return (False, None) if self.released else (True, np.zeros((20, 30, 3), dtype=np.uint8))

    def release(self):
        self.released = True


def test_saved_rtsp_camera_hides_password_and_reconnects_after_a_drop(client, monkeypatch):
    project_id = client.post("/projects", json={"name": "RTSP preview"}).json()["id"]
    saved = client.post(f"/projects/{project_id}/cameras/rtsp", json={
        "name": "Receiving dock", "url": "rtsp://camera.local/live", "username": "operator", "password": "not-returned",
    })
    assert saved.status_code == 201, saved.text
    camera = saved.json()
    assert camera["has_password"] is True and "password" not in camera
    assert client.get(f"/projects/{project_id}/cameras/rtsp").json()["cameras"] == [camera]

    usable = _Capture()
    attempts = iter([_DroppedCapture(), usable])
    monkeypatch.setattr(camera_sessions, "_open_rtsp_capture", lambda _url: next(attempts))
    started = client.post(f"/projects/{project_id}/cameras/rtsp/{camera['id']}/sessions")
    assert started.status_code == 201, started.text
    session_id = started.json()["id"]
    frame = None
    for _ in range(35):
        frame = client.get(f"/projects/{project_id}/cameras/rtsp/sessions/{session_id}/frame")
        if frame.status_code == 200:
            break
        time.sleep(0.03)
    assert frame is not None and frame.status_code == 200
    state = client.get(f"/projects/{project_id}/cameras/rtsp/sessions/{session_id}").json()
    assert state["source_type"] == "rtsp" and state["camera_name"] == "Receiving dock" and state["reconnect_count"] >= 1
    assert client.delete(f"/projects/{project_id}/cameras/rtsp/sessions/{session_id}").status_code == 204
    assert usable.released is True
