from fastapi.testclient import TestClient
import pytest

from app import db, events
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        yield client, root


def test_line_cross_event_persists_metadata_and_jpeg_snapshot(workspace):
    client, root = workspace
    project = client.post("/projects", json={"name": "Event storage"}).json()
    project_id = project["id"]
    created = events.record_line_cross(
        db.database_path(root), root, project_id, None, "Apple", 7, 0.88, 3, b"jpeg-event-bytes",
    )
    assert created.event_type == "line_cross" and created.snapshot_url
    listed = client.get(f"/projects/{project_id}/events")
    assert listed.status_code == 200, listed.text
    event = listed.json()["events"][0]
    assert event["class_name"] == "Apple" and event["track_id"] == 7 and event["count"] == 3
    snapshot = client.get(event["snapshot_url"])
    assert snapshot.status_code == 200 and snapshot.headers["content-type"] == "image/jpeg"
    assert snapshot.content == b"jpeg-event-bytes"
