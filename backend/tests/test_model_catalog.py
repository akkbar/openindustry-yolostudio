import uuid

import pytest
from fastapi.testclient import TestClient

from app import camera_sessions, db, model_catalog
from app.errors import AppError
from app.main import app
from app.projects import _now


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        yield client, root


def project(client, name="Catalog project"):
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_catalog_has_unique_metadata_driven_entries_and_search_filters(workspace):
    client, _ = workspace
    response = client.get("/model-catalog")
    assert response.status_code == 200
    catalog = response.json()
    assert len(catalog["models"]) >= 20
    assert len({item["id"] for item in catalog["models"]}) == len(catalog["models"])
    assert {"General", "People", "Safety", "Logistics", "Manufacturing"} <= set(catalog["categories"])
    person = client.get("/model-catalog", params={"query": "person"}).json()["models"]
    assert {"person-detection", "person-counter", "ppe-detection", "person-forklift-safety"} <= {item["id"] for item in person}
    safety = client.get("/model-catalog", params={"category": "Safety"}).json()["models"]
    assert safety and all(item["category"] == "Safety" for item in safety)
    assert client.get("/model-catalog", params={"query": "helmet"}).json()["models"][0]["id"] in {"ppe-detection", "helmet-detection"}


def test_catalog_rejects_duplicate_ids_and_shares_the_bundled_base_model(workspace):
    _, root = workspace
    duplicate = (model_catalog.CATALOG[0], model_catalog.CATALOG[0])
    with pytest.raises(RuntimeError, match="duplicate"):
        model_catalog.validate_catalog(duplicate)
    with db.session(db.database_path(root)) as connection:
        person_path, person_filter, _ = model_catalog.runtime_model(connection, root, "person-detection")
        vehicle_path, vehicle_filter, _ = model_catalog.runtime_model(connection, root, "vehicle-detection")
    assert person_path == vehicle_path
    assert person_filter == ("person",)
    assert vehicle_filter == ("car", "truck", "bus", "motorcycle")


def test_downloadable_status_and_missing_artifact_fail_cleanly(workspace):
    client, root = workspace
    helmet = client.get("/model-catalog/models/helmet-detection").json()
    assert helmet["status"] == "AVAILABLE"
    response = client.post("/model-catalog/models/helmet-detection/install")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "model_download_unavailable"
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("INSERT INTO catalog_model_installations VALUES ('helmet-detection', 'INSTALLED', '1.0.0', 'models/downloaded/helmet-detection.pt', NULL, NULL, ?)", (_now(),))
    with db.session(db.database_path(root)) as connection:
        with pytest.raises(AppError) as failure:
            model_catalog.runtime_model(connection, root, "helmet-detection")
    assert failure.value.code == "catalog_model_artifact_missing"


def test_project_can_select_pretrained_model_then_custom_model_remains_available(workspace):
    client, root = workspace
    project_id = project(client)
    selected = client.put(f"/model-catalog/projects/{project_id}/selection", json={"model_id": "bottle-detection"})
    assert selected.status_code == 200, selected.text
    assert selected.json()["model"]["id"] == "bottle-detection"
    with db.session(db.database_path(root)) as connection:
        row = connection.execute("SELECT active_model_id, catalog_model_id, catalog_model_settings FROM projects WHERE id = ?", (project_id,)).fetchone()
    assert row["active_model_id"] is None and row["catalog_model_id"] == "bottle-detection"
    assert '"class_filter":["bottle"]' in row["catalog_model_settings"]

    model_id = uuid.uuid4().hex
    path = root / "projects" / project_id / "models" / f"{model_id}.pt"
    path.write_bytes(b"custom")
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("INSERT INTO models (id, project_id, name, version, status, relative_path, metrics, created_at, settings) VALUES (?, ?, 'Custom model', 1, 'development', ?, '{}', ?, '{}')", (model_id, project_id, f"models/{model_id}.pt", _now()))
    activated = client.post(f"/projects/{project_id}/models/{model_id}/activate")
    assert activated.status_code == 200
    with db.session(db.database_path(root)) as connection:
        row = connection.execute("SELECT active_model_id, catalog_model_id FROM projects WHERE id = ?", (project_id,)).fetchone()
    assert tuple(row) == (model_id, None)


def test_catalog_selection_runs_shared_model_with_its_class_filter(workspace, monkeypatch):
    client, _ = workspace
    project_id = project(client, "Catalog camera")
    assert client.put(f"/model-catalog/projects/{project_id}/selection", json={"model_id": "person-detection"}).status_code == 200

    class Values:
        def __init__(self, value): self.value = value
        def tolist(self): return self.value
    class Boxes:
        xyxy = Values([[8, 4, 48, 24], [0, 0, 20, 20]])
        conf = Values([0.8, 0.9])
        cls = Values([0, 2])
    class Result:
        boxes = Boxes()
        names = {0: "person", 2: "car"}
    monkeypatch.setattr(camera_sessions, "_load_yolo", lambda _: lambda *_args, **_kwargs: [Result()])
    frame = type("Frame", (), {"shape": (40, 80, 3)})()
    detections = camera_sessions._infer(camera_sessions._load_yolo(None), frame, ("person",))
    assert [item.class_name for item in detections] == ["person"]
