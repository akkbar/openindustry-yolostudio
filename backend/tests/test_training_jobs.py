from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    return root


@pytest.fixture
def client(data_root):
    with TestClient(app) as client:
        yield client


def create_project(client, name="Training jobs"):
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def jobs_url(project_id):
    return f"/projects/{project_id}/training-jobs"


def create_job(client, project_id, payload=None):
    response = client.post(jobs_url(project_id), json=payload or {})
    assert response.status_code == 201, response.text
    return response.json()


def test_training_job_is_queued_persisted_and_listed(client, data_root):
    project_id = create_project(client)
    first = create_job(client, project_id, {"epochs": 12, "imgsz": 320})
    second = create_job(client, project_id)

    assert first == client.get(f"{jobs_url(project_id)}/{first['id']}").json()
    assert first["project_id"] == project_id
    assert first["status"] == "queued"
    assert first["model"] == "yolo11n"
    assert (first["epochs"], first["imgsz"], first["progress"]) == (12, 320, 0)
    assert first["metrics"] is None and first["error"] is None
    assert first["started_at"] is None and first["finished_at"] is None
    assert first["created_at"].endswith("Z")
    assert (second["epochs"], second["imgsz"]) == (50, 640)

    listing = client.get(jobs_url(project_id)).json()
    assert listing["total"] == 2
    assert [job["id"] for job in listing["jobs"]] == [second["id"], first["id"]]
    assert (listing["offset"], listing["limit"]) == (0, 30)

    with db.session(db.database_path(data_root)) as connection:
        row = connection.execute(
            "SELECT model, epochs, imgsz, device, status, progress, updated_at "
            "FROM training_jobs WHERE id = ?", (first["id"],)
        ).fetchone()
    assert dict(row) == {
        "model": "yolo11n", "epochs": 12, "imgsz": 320, "device": "auto",
        "status": "queued", "progress": 0.0, "updated_at": first["created_at"],
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"model": "other.pt"},
        {"epochs": 0},
        {"epochs": 10_001},
        {"imgsz": 31},
        {"imgsz": 4_097},
        {"unexpected": "value"},
    ],
)
def test_training_job_configuration_is_bounded_and_english(client, payload):
    project_id = create_project(client)
    response = client.post(jobs_url(project_id), json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert response.json()["error"]["message"].endswith(".")
    assert client.get(jobs_url(project_id)).json()["total"] == 0


def test_training_job_cancellation_is_durable_and_idempotent(client, data_root):
    project_id = create_project(client)
    queued = create_job(client, project_id)
    cancelled = client.post(f"{jobs_url(project_id)}/{queued['id']}/cancel")
    assert cancelled.status_code == 200
    cancelled = cancelled.json()
    assert cancelled["status"] == "cancelled"
    assert cancelled["finished_at"].endswith("Z")
    assert cancelled["started_at"] is None
    assert client.post(f"{jobs_url(project_id)}/{queued['id']}/cancel").json() == cancelled

    running = create_job(client, project_id)
    with db.transaction(db.database_path(data_root)) as connection:
        connection.execute(
            "UPDATE training_jobs SET status = 'running', started_at = ? WHERE id = ?",
            (running["created_at"], running["id"]),
        )
    stopped = client.post(f"{jobs_url(project_id)}/{running['id']}/cancel").json()
    assert stopped["status"] == "cancelled"
    assert stopped["started_at"] == running["created_at"]

    completed = create_job(client, project_id)
    with db.transaction(db.database_path(data_root)) as connection:
        connection.execute(
            "UPDATE training_jobs SET status = 'completed', finished_at = ? WHERE id = ?",
            (completed["created_at"], completed["id"]),
        )
    response = client.post(f"{jobs_url(project_id)}/{completed['id']}/cancel")
    assert response.status_code == 409
    assert response.json()["error"] == {
        "code": "training_job_not_cancellable",
        "message": "This training job has already finished and cannot be cancelled.",
    }


def test_training_jobs_are_scoped_to_their_project_and_cascade_on_delete(client, data_root):
    project_id = create_project(client, "Owned jobs")
    other_project = create_project(client, "Other jobs")
    job = create_job(client, project_id)

    hidden = client.get(f"{jobs_url(other_project)}/{job['id']}")
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "training_job_not_found"
    assert client.post(jobs_url("0" * 32), json={}).status_code == 404

    assert client.delete(f"/projects/{project_id}").status_code == 204
    with db.session(db.database_path(data_root)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM training_jobs WHERE project_id = ?", (project_id,)).fetchone()[0] == 0


def test_migration_six_renames_legacy_training_columns(data_root):
    path = db.database_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    project_id = "a" * 32
    job_id = "b" * 32
    now = "2026-09-16T00:00:00.000000Z"

    with db.transaction(path) as connection:
        for version, statements in db.MIGRATIONS:
            if version > 5:
                break
            for statement in statements:
                connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {version}")
        connection.execute(
            "INSERT INTO projects VALUES (?, 'Legacy project', 'legacy project', '', "
            "'object_detection', ?, ?)",
            (project_id, now, now),
        )
        connection.execute(
            "INSERT INTO training_jobs "
            "(id, project_id, status, base_model, epochs, image_size, device, progress, metrics, "
            "error, created_at, started_at, finished_at) "
            "VALUES (?, ?, 'queued', 'yolo11n', 50, 640, 'auto', 0, NULL, NULL, ?, NULL, NULL)",
            (job_id, project_id, now),
        )

    db.initialize_database(data_root)
    with db.session(path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(training_jobs)")}
        row = connection.execute(
            "SELECT model, imgsz, updated_at FROM training_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    assert {"model", "imgsz", "updated_at"} <= columns
    assert "base_model" not in columns and "image_size" not in columns
    assert dict(row) == {"model": "yolo11n", "imgsz": 640, "updated_at": now}
