import io
import json
import sys
import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import base_models, db, training_jobs, training_worker, vision_runtime
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        yield client, root


def create_project(client, name="Training worker"):
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_job(client, project_id, **payload):
    response = client.post(f"/projects/{project_id}/training-jobs", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def add_valid_dataset(client, project_id):
    class_id = client.post(f"/projects/{project_id}/classes", json={"name": "Object"}).json()["id"]
    for index in range(2):
        output = io.BytesIO()
        Image.new("RGB", (64, 64), (index * 80, 40, 120)).save(output, "PNG")
        image = client.post(
            f"/projects/{project_id}/datasets/images?filename=frame-{index}.png",
            content=output.getvalue(),
        ).json()["image"]
        response = client.post(
            f"/projects/{project_id}/datasets/images/{image['id']}/annotations",
            json={
                "id": uuid.uuid4().hex,
                "class_id": class_id,
                "center_x": 0.5,
                "center_y": 0.5,
                "width": 0.4,
                "height": 0.3,
                "expected_revision": 0,
            },
        )
        assert response.status_code == 201, response.text


def wait_for_terminal_job(client, project_id, job_id, timeout=45):
    deadline = time.monotonic() + timeout
    result = None
    while time.monotonic() < deadline:
        result = client.get(f"/projects/{project_id}/training-jobs/{job_id}").json()
        if result["status"] in {"completed", "failed", "cancelled"}:
            return result
        time.sleep(0.1)
    raise AssertionError(f"Training worker did not finish: {result}")


def test_start_launches_a_separate_worker_without_blocking_the_backend(workspace):
    client, root = workspace
    project_id = create_project(client)
    job = create_job(client, project_id, epochs=1, imgsz=32)

    started_at = time.monotonic()
    started = client.post(f"/projects/{project_id}/training-jobs/{job['id']}/start")
    elapsed = time.monotonic() - started_at

    assert started.status_code == 202, started.text
    assert elapsed < 3
    assert started.json()["status"] == "running"
    assert started.json()["started_at"].endswith("Z")
    assert client.get("/health").json()["status"] == "ok"

    failed = wait_for_terminal_job(client, project_id, job["id"])
    assert failed["status"] == "failed"
    assert failed["error"] == training_worker.DATASET_NOT_READY
    worker_log = root / "logs" / "training-workers" / f"{job['id']}.log"
    assert worker_log.is_file()
    assert f"Training worker started for job {job['id']}." in worker_log.read_text(encoding="utf-8")


def test_worker_exports_a_snapshot_then_persists_a_completed_job(workspace, monkeypatch):
    client, root = workspace
    project_id = create_project(client)
    add_valid_dataset(client, project_id)
    queued = create_job(client, project_id, epochs=2, imgsz=64)
    database = db.database_path(root)
    training_jobs.claim_training_job(database, project_id, queued["id"])
    local_model = root / "models" / "base" / "yolo11n.pt"
    local_model.parent.mkdir(parents=True, exist_ok=True)
    local_model.write_bytes(b"local model placeholder")
    calls = {}

    monkeypatch.setattr(vision_runtime, "initialize_runtime", lambda _: {"status": "ready"})
    monkeypatch.setattr(
        base_models,
        "provision_base_model",
        lambda _: {"path": str(local_model)},
    )

    def fake_train(database_path, job, model_path, data_yaml, run_directory):
        calls.update(
            database_path=database_path,
            job=job,
            model_path=model_path,
            data_yaml=data_yaml,
            run_directory=run_directory,
        )
        return {"metrics/mAP50(B)": 0.75, "metrics/precision(B)": 0.8}

    monkeypatch.setattr(training_worker, "run_ultralytics_training", fake_train)

    assert training_worker.run_training_job(queued["id"], root) == 0
    completed = client.get(f"/projects/{project_id}/training-jobs/{queued['id']}").json()
    assert completed["status"] == "completed"
    assert completed["progress"] == 1
    assert completed["metrics"] == {"metrics/mAP50(B)": 0.75, "metrics/precision(B)": 0.8}
    assert completed["error"] is None and completed["finished_at"].endswith("Z")
    assert calls["database_path"] == database
    assert calls["model_path"] == local_model
    assert calls["data_yaml"].is_file()
    assert calls["data_yaml"].parent.parent.name == "dataset-export"
    context = json.loads((calls["run_directory"] / "training-context.json").read_text(encoding="utf-8"))
    assert context["job_id"] == queued["id"]
    assert context["model_path"] == str(local_model)
    assert context["dataset_yaml"] == str(calls["data_yaml"])


def test_ultralytics_runner_uses_the_local_cpu_configuration_and_checkpoints_metrics(
    workspace, monkeypatch
):
    client, root = workspace
    project_id = create_project(client)
    queued = create_job(client, project_id, epochs=2, imgsz=64)
    database = db.database_path(root)
    training_jobs.claim_training_job(database, project_id, queued["id"])
    job = training_jobs.read_running_training_job(database, queued["id"])
    run_directory = root / "projects" / project_id / "runs" / queued["id"]
    run_directory.mkdir(parents=True)
    data_yaml = run_directory / "data.yaml"
    data_yaml.write_text("path: /local/dataset\n", encoding="utf-8")

    class FakeMetricResult:
        results_dict = {"metrics/mAP50(B)": 0.75}

    class FakeTrainer:
        epoch = 0
        tloss = {"train/box_loss": 0.25, "train/cls_loss": 0.1}
        metrics = {"metrics/precision(B)": 0.8, "metrics/recall(B)": 0.7}
        stop = False

    class FakeYOLO:
        task = "detect"

        def __init__(self):
            self.callbacks = {}
            self.kwargs = None
            self.metrics = FakeMetricResult()

        def add_callback(self, event, callback):
            self.callbacks.setdefault(event, []).append(callback)

        def train(self, **kwargs):
            self.kwargs = kwargs
            trainer = FakeTrainer()
            for callback in self.callbacks["on_fit_epoch_end"]:
                callback(trainer)
            return FakeMetricResult()

    model = FakeYOLO()
    monkeypatch.setattr(training_worker, "_load_yolo", lambda _: model)
    metrics = training_worker.run_ultralytics_training(
        database, job, root / "models" / "base" / "yolo11n.pt", data_yaml, run_directory
    )

    assert model.kwargs == {
        "data": str(data_yaml),
        "epochs": 2,
        "imgsz": 64,
        "device": "cpu",
        "workers": 0,
        "project": str(run_directory.parent),
        "name": queued["id"],
        "exist_ok": True,
        "plots": False,
        "save": True,
    }
    assert metrics == {
        "train/box_loss": 0.25,
        "train/cls_loss": 0.1,
        "metrics/precision(B)": 0.8,
        "metrics/recall(B)": 0.7,
        "metrics/mAP50(B)": 0.75,
    }
    persisted = client.get(f"/projects/{project_id}/training-jobs/{queued['id']}").json()
    assert persisted["progress"] == 0.5
    assert persisted["metrics"] == {
        "train/box_loss": 0.25,
        "train/cls_loss": 0.1,
        "metrics/precision(B)": 0.8,
        "metrics/recall(B)": 0.7,
    }


def test_cancelled_job_does_not_initialize_or_execute_a_worker(workspace, monkeypatch):
    client, root = workspace
    project_id = create_project(client)
    queued = create_job(client, project_id)
    assert client.post(f"/projects/{project_id}/training-jobs/{queued['id']}/cancel").status_code == 200
    monkeypatch.setattr(
        training_worker.vision_runtime,
        "initialize_runtime",
        lambda _: pytest.fail("A cancelled job must not initialize the runtime."),
    )

    assert training_worker.run_training_job(queued["id"], root) == 0
    assert client.get(f"/projects/{project_id}/training-jobs/{queued['id']}").json()["status"] == "cancelled"


def test_project_deletion_waits_for_a_running_training_job(workspace):
    client, root = workspace
    project_id = create_project(client)
    queued = create_job(client, project_id)
    training_jobs.claim_training_job(db.database_path(root), project_id, queued["id"])

    blocked = client.delete(f"/projects/{project_id}")
    assert blocked.status_code == 409
    assert blocked.json()["error"] == {
        "code": "project_training_active",
        "message": "A training job is still running. Cancel it and wait for the worker to stop before deleting this project.",
    }
    assert client.post(f"/projects/{project_id}/training-jobs/{queued['id']}/cancel").status_code == 200
    assert client.delete(f"/projects/{project_id}").status_code == 204


def test_worker_command_uses_the_frozen_executable_when_available(monkeypatch):
    job_id = "a" * 32
    with monkeypatch.context() as patch:
        patch.setattr(training_worker.sys, "frozen", True, raising=False)
        patch.setattr(training_worker.sys, "executable", "C:/Vision Studio/backend.exe")
        assert training_worker.worker_command(job_id) == [
            "C:/Vision Studio/backend.exe",
            "--training-worker",
            job_id,
        ]
    assert training_worker.worker_command(job_id) == [
        sys.executable,
        "-m",
        "app",
        "--training-worker",
        job_id,
    ]
