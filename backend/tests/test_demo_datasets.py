import io
import shutil
import time
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db, demo_datasets
from app.main import app


def _image_bytes(color):
    output = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(output, "JPEG")
    return output.getvalue()


def _archive(path, images=2, labels=2, metadata=False):
    with zipfile.ZipFile(path, "w") as target:
        for index in range(images):
            target.writestr(f"images/apple-{index}.jpg", _image_bytes((index * 30, 90, 50)))
        for index in range(labels):
            target.writestr(f"labels/apple-{index}.txt", "0 0.5 0.5 0.4 0.5\n")
        if metadata:
            target.writestr("labels/labels.txt", "apple\n")


def _wait(client, status):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = client.get("/demo-datasets/apple")
        assert result.status_code == 200, result.text
        if result.json()["status"] == status:
            return result.json()
        time.sleep(0.01)
    pytest.fail(f"Demo import did not reach {status}.")


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    archive = tmp_path / "apple.zip"
    _archive(archive)
    monkeypatch.setattr(demo_datasets, "EXPECTED_IMAGES", 2)

    def copy_archive(data_root, job):
        destination = demo_datasets.demo_archive_path(data_root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, destination)
        job.update(progress=1, message="Download complete.")
        return destination

    monkeypatch.setattr(demo_datasets, "download_archive", copy_archive)
    with TestClient(app) as client:
        yield client, root, archive


def test_downloads_full_demo_archive_and_imports_yolo_annotations(workspace):
    client, root, _ = workspace
    initial = client.get("/demo-datasets/apple").json()
    assert initial["status"] == "not_started"
    assert initial["image_count"] == 2

    assert client.post("/demo-datasets/apple").status_code == 202
    result = _wait(client, "completed")
    project_id = result["project_id"]
    assert project_id
    assert client.get(f"/projects/{project_id}/datasets/summary").json() == {"image_count": 2}
    classes = client.get(f"/projects/{project_id}/classes").json()
    assert [(item["class_index"], item["name"], item["annotation_count"]) for item in classes["classes"]] == [(0, "apple", 2)]
    images = client.get(f"/projects/{project_id}/datasets/images?offset=0&limit=60").json()["images"]
    assert len(images) == 2 and all(image["annotated"] for image in images)
    for image in images:
        annotations = client.get(f"/projects/{project_id}/datasets/images/{image['id']}/annotations").json()
        assert len(annotations["annotations"]) == 1
    with db.session(db.database_path(root)) as connection:
        record = connection.execute("SELECT source_url, license FROM demo_dataset_imports").fetchone()
        assert tuple(record) == (demo_datasets.SOURCE_URL, demo_datasets.SOURCE_LICENSE)
    assert client.post("/demo-datasets/apple").json()["project_id"] == project_id


def test_rejects_an_incomplete_archive_without_creating_a_project(workspace):
    client, _, archive = workspace
    _archive(archive, images=2, labels=1)
    assert client.post("/demo-datasets/apple").status_code == 202
    result = _wait(client, "failed")
    assert "matching YOLO label" in result["error"]
    assert client.get("/projects").json()["total"] == 0


def test_ignores_the_source_class_metadata_label_file(workspace):
    client, _, archive = workspace
    _archive(archive, metadata=True)
    assert client.post("/demo-datasets/apple").status_code == 202
    result = _wait(client, "completed")
    assert result["project_id"]


def test_ignores_zero_area_source_placeholders_but_keeps_valid_boxes():
    labels = demo_datasets._parse_yolo_labels(b"0 1.0 0.0 0.0 0.0\n0 0.5 0.5 0.4 0.5\n")
    assert labels == [(0.5, 0.5, 0.4, 0.5)]


def test_completed_demo_is_available_after_restart(workspace):
    client, _, _ = workspace
    client.post("/demo-datasets/apple")
    completed = _wait(client, "completed")
    with TestClient(app) as reopened:
        result = reopened.get("/demo-datasets/apple").json()
    assert result["status"] == "completed"
    assert result["project_id"] == completed["project_id"]
    assert result["archive_bytes"] > 0
