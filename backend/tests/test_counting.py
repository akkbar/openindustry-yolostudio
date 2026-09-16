from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import counting
from app.main import app


def detection(x, y=0.4, width=0.3, height=0.2, confidence=0.9, name="banana"):
    return SimpleNamespace(x=x, y=y, width=width, height=height, confidence=confidence, class_name=name)


def test_bytetrack_keeps_an_id_and_counts_one_segment_crossing():
    line = counting.LineConfig("line-1", "Banana Count", (0.5, 0.0), (0.5, 1.0), "both", True)
    tracker = counting.ByteTrackTracker()
    counter = counting.CrossingCounter((line,))

    first = tracker.update([detection(0.2, width=0.5)])
    counter.observe(first)
    second = tracker.update([detection(0.3, width=0.5)])
    crossings = counter.observe(second)
    third = tracker.update([detection(0.35, width=0.5)])
    assert counter.observe(third) == []

    assert first[0].track_id == second[0].track_id == third[0].track_id
    assert len(crossings) == 1 and crossings[0].count == 1 and crossings[0].observation.track_id == first[0].track_id
    assert counter.snapshot() == [{"line_id": "line-1", "line_name": "Banana Count", "count": 1, "a_to_b": 0, "b_to_a": 1}]


def test_roi_filters_detections_before_tracking():
    roi = counting.RoiConfig(((0.0, 0.0), (0.5, 0.0), (0.5, 1.0), (0.0, 1.0)), True)
    kept = counting.filter_roi([detection(0.1), detection(0.7)], roi)
    assert kept == [kept[0]]
    assert kept[0].x == 0.1


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(tmp_path / "VisionStudio"))
    with TestClient(app) as test_client:
        yield test_client


def test_counting_configuration_persists_normalized_line_and_roi(client):
    project = client.post("/projects", json={"name": "Counting setup"}).json()
    project_id = project["id"]
    created = client.post(f"/projects/{project_id}/counting/lines", json={
        "name": "Inbound", "start": {"x": 0.1, "y": 0.5}, "end": {"x": 0.9, "y": 0.5}, "direction": "a_to_b",
    })
    assert created.status_code == 201, created.text
    line = created.json()
    assert line["start"] == {"x": 0.1, "y": 0.5}
    saved = client.put(f"/projects/{project_id}/counting/roi", json={
        "points": [{"x": 0.1, "y": 0.1}, {"x": 0.9, "y": 0.1}, {"x": 0.5, "y": 0.9}],
    })
    assert saved.status_code == 200, saved.text
    configuration = client.get(f"/projects/{project_id}/counting").json()
    assert configuration["lines"] == [line]
    assert configuration["roi"]["points"][2] == {"x": 0.5, "y": 0.9}
    assert client.post(f"/projects/{project_id}/counting/lines", json={
        "name": "Invalid", "start": {"x": 0.5, "y": 0.5}, "end": {"x": 0.5, "y": 0.5},
    }).status_code == 422
