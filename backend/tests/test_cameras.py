import pytest
from fastapi.testclient import TestClient

from app import cameras
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(tmp_path / "VisionStudio"))
    with TestClient(app) as client:
        yield client


def test_usb_scan_returns_only_opened_cameras_and_releases_every_handle(client, monkeypatch):
    opened = {0: True, 1: False, 2: True}
    handles = []

    class Capture:
        def __init__(self, index): self.index, self.released = index, False
        def isOpened(self): return opened[self.index]
        def release(self): self.released = True

    def open_capture(index):
        capture = Capture(index)
        handles.append(capture)
        return capture

    monkeypatch.setattr(cameras, "_open_capture", open_capture)
    response = client.get("/cameras/usb?limit=3")
    assert response.status_code == 200
    assert response.json() == {
        "cameras": [
            {"id": "usb-0", "index": 0, "name": "Camera 0", "source_type": "usb"},
            {"id": "usb-2", "index": 2, "name": "Camera 2", "source_type": "usb"},
        ],
        "scanned": 3,
    }
    assert [capture.released for capture in handles] == [True, True, True]


def test_usb_scan_limit_is_bounded_and_english(client):
    response = client.get("/cameras/usb?limit=0")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["error"]["message"].endswith(".")
