import json

import pytest
from fastapi.testclient import TestClient

from app import db, model_registry, training_jobs
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        yield client, root


def create_project(client):
    response = client.post("/projects", json={"name": "Registry project"})
    assert response.status_code == 201
    return response.json()["id"]


def create_completed_model(client, root, project_id):
    job = client.post(f"/projects/{project_id}/training-jobs", json={"epochs": 2, "imgsz": 64}).json()
    database = db.database_path(root)
    training_jobs.claim_training_job(database, project_id, job["id"])
    run = root / "projects" / project_id / "runs" / job["id"]
    (run / "weights").mkdir(parents=True)
    (run / "weights" / "best.pt").write_bytes(b"trained checkpoint")
    (run / "training-context.json").write_text(json.dumps({"dataset_export_id": "snapshot-1"}), encoding="utf-8")
    metrics = {"metrics/mAP50(B)": 0.75, "metrics/precision(B)": 0.8}
    assert training_jobs.complete_training_job(database, job["id"], metrics)
    with db.session(database) as connection:
        record = dict(connection.execute("SELECT * FROM training_jobs WHERE id = ?", (job["id"],)).fetchone())
    model_id = model_registry.register_completed_training_job(database, root, record, run, metrics)
    assert model_id is not None
    return job, model_id


def test_completed_training_registers_checkpoint_metadata_and_active_selection(workspace):
    client, root = workspace
    project_id = create_project(client)
    job, model_id = create_completed_model(client, root, project_id)

    listing = client.get(f"/projects/{project_id}/models")
    assert listing.status_code == 200
    registered = listing.json()["models"]
    assert len(registered) == 1
    model = registered[0]
    assert model == {
        "id": model_id, "project_id": project_id, "training_job_id": job["id"],
        "name": "Registry project v1", "version": 1, "status": "development",
        "path": str(root / "projects" / project_id / "models" / f"{model_id}.pt"),
        "dataset_export_id": "snapshot-1", "settings": {"model": "yolo11n", "epochs": 2, "imgsz": 64, "device": "auto"},
        "metrics": {"metrics/mAP50(B)": 0.75, "metrics/precision(B)": 0.8},
        "created_at": model["created_at"], "active": False,
    }
    assert (root / "projects" / project_id / "models" / f"{model_id}.pt").read_bytes() == b"trained checkpoint"

    renamed = client.patch(f"/projects/{project_id}/models/{model_id}", json={"name": "pallet-v1"}).json()
    assert renamed["name"] == "pallet-v1"
    active = client.post(f"/projects/{project_id}/models/{model_id}/activate").json()
    assert active["status"] == "production" and active["active"] is True
    archived = client.post(f"/projects/{project_id}/models/{model_id}/archive").json()
    assert archived["status"] == "archived" and archived["active"] is False
    assert client.get(f"/projects/{project_id}/models").json()["active_model_id"] is None


def test_registry_is_idempotent_for_one_completed_job(workspace):
    client, root = workspace
    project_id = create_project(client)
    job, model_id = create_completed_model(client, root, project_id)
    database = db.database_path(root)
    with db.session(database) as connection:
        record = dict(connection.execute("SELECT * FROM training_jobs WHERE id = ?", (job["id"],)).fetchone())
    run = root / "projects" / project_id / "runs" / job["id"]
    assert model_registry.register_completed_training_job(database, root, record, run, {"metrics/mAP50(B)": 0.75}) == model_id
    assert len(client.get(f"/projects/{project_id}/models").json()["models"]) == 1
