"""Separate-process CPU training for the durable training-job contract."""

from __future__ import annotations

import json
import logging
import math
import os
import re
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from app import base_models, dataset_export, db, model_registry, storage, training_jobs, vision_runtime
from app.errors import AppError


JOB_ID_PATTERN = re.compile(r"[0-9a-f]{32}")
DATASET_NOT_READY = (
    "The project dataset is not ready for training. Add at least two annotated images "
    "and validate the dataset before starting training."
)
TRAINING_FAILED = "Training failed in the worker process. Check the worker log and retry."
WORKER_EXITED = "The training worker exited before completing the job."
INTERRUPTED = "Training was interrupted when the local backend stopped. Create a new job to retry."
MAX_METRICS = 32


def _job_run_directory(data_root: Path, project_id: str, job_id: str) -> Path:
    """Create only the project-owned directory for a generated job identifier."""
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("The training job identifier is invalid.")
    project = storage.create_project_directories(data_root, project_id)
    runs = project / "runs"
    if runs.resolve().parent != project.resolve():
        raise OSError("Training runs must remain inside the project folder.")
    target = runs / job_id
    if target.resolve().parent != runs.resolve():
        raise OSError("The training run path is invalid.")
    target.mkdir(exist_ok=True)
    return target


def worker_command(job_id: str) -> list[str]:
    """Use the same entry executable in a child-only worker mode when frozen."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--training-worker", job_id]
    return [sys.executable, "-m", "app", "--training-worker", job_id]


def _worker_output_log(data_root: Path, job_id: str) -> Path:
    """Keep a child-owned handle out of a project folder that users may delete."""
    if not JOB_ID_PATTERN.fullmatch(job_id):
        raise ValueError("The training job identifier is invalid.")
    logs = data_root / "logs"
    if logs.resolve() != logs:
        raise OSError("Training worker logs must not redirect outside application data.")
    directory = logs / "training-workers"
    directory.mkdir(parents=True, exist_ok=True)
    if directory.resolve() != directory or directory.resolve().parent != logs.resolve():
        raise OSError("Training worker logs must remain inside application data.")
    target = directory / f"{job_id}.log"
    if target.resolve().parent != directory.resolve():
        raise OSError("The training worker log path is invalid.")
    return target


def _numeric_metrics(*sources: Any) -> dict[str, float]:
    """Persist only finite scalar values from Ultralytics' evolving metric objects."""
    metrics: dict[str, float] = {}
    for source in sources:
        if source is None:
            continue
        if not isinstance(source, Mapping):
            source = getattr(source, "results_dict", source)
        if not isinstance(source, Mapping):
            continue
        for key, value in source.items():
            name = str(key)
            if not name or len(name) > 120:
                continue
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number):
                metrics[name] = number
                if len(metrics) >= MAX_METRICS:
                    return metrics
    return metrics


def _load_yolo(model_path: Path):
    """Load a local checkpoint after disabling Ultralytics' update lookup in workers."""
    from ultralytics.utils import checks

    checks.ONLINE = False
    from ultralytics import YOLO

    return YOLO(str(model_path))


def run_ultralytics_training(
    database: Path,
    job: dict,
    model_path: Path,
    data_yaml: Path,
    run_directory: Path,
) -> dict[str, float]:
    """Train one local detection checkpoint and save short progress checkpoints."""
    model = _load_yolo(model_path)
    if getattr(model, "task", None) != "detect":
        raise RuntimeError("The configured base model is not an object-detection checkpoint.")

    current_metrics: dict[str, float] = {}

    def cancelled() -> bool:
        return training_jobs.training_job_status(database, job["id"]) != "running"

    def observe_cancellation(trainer) -> None:
        if cancelled():
            trainer.stop = True

    def checkpoint(trainer) -> None:
        nonlocal current_metrics
        current_metrics = _numeric_metrics(
            getattr(trainer, "tloss", None),
            getattr(trainer, "metrics", None),
            getattr(getattr(trainer, "validator", None), "metrics", None),
        )
        try:
            epoch = int(getattr(trainer, "epoch", -1))
        except (TypeError, ValueError):
            epoch = -1
        progress = (epoch + 1) / job["epochs"] if epoch >= 0 else 0.0
        training_jobs.update_training_job_progress(database, job["id"], progress, current_metrics)
        observe_cancellation(trainer)

    # Batch-level cancellation does not write progress, so it remains cheap while
    # allowing the database cancellation request to stop CPU work promptly.
    model.add_callback("on_train_batch_end", observe_cancellation)
    model.add_callback("on_fit_epoch_end", checkpoint)
    results = model.train(
        data=str(data_yaml),
        epochs=job["epochs"],
        imgsz=job["imgsz"],
        device="cpu",
        workers=0,
        project=str(run_directory.parent),
        name=job["id"],
        exist_ok=True,
        plots=False,
        save=True,
    )
    return _numeric_metrics(current_metrics, results, getattr(model, "metrics", None))


def _write_job_context(run_directory: Path, job: dict, model_path: Path, snapshot: dict) -> None:
    """Keep the immutable input and local output relationship beside the run."""
    context = {
        "job_id": job["id"],
        "project_id": job["project_id"],
        "model": job["model"],
        "model_path": str(model_path),
        "epochs": job["epochs"],
        "imgsz": job["imgsz"],
        "dataset_export_id": snapshot["export_id"],
        "dataset_yaml": snapshot["yaml_path"],
    }
    (run_directory / "training-context.json").write_text(
        json.dumps(context, indent=2) + "\n", encoding="utf-8"
    )


def run_training_job(job_id: str, data_root: Path) -> int:
    """Run a single claimed job in the child process and return its exit code."""
    if not JOB_ID_PATTERN.fullmatch(job_id):
        logging.error("The training worker received an invalid job identifier.")
        return 2

    print(f"Training worker started for job {job_id}.", flush=True)
    database = db.initialize_database(data_root)
    job = training_jobs.read_running_training_job(database, job_id)
    if job is None:
        if training_jobs.training_job_status(database, job_id) == "cancelled":
            print(f"Training worker stopped because job {job_id} was cancelled.", flush=True)
            return 0
        logging.error("The training worker could not find a running job.")
        return 1

    try:
        vision_runtime.initialize_runtime(data_root)
        model_info = base_models.provision_base_model(data_root)
        model_path = Path(model_info["path"])
        run_directory = _job_run_directory(data_root, job["project_id"], job_id)
        if training_jobs.training_job_status(database, job_id) != "running":
            print(f"Training worker stopped because job {job_id} was cancelled.", flush=True)
            return 0

        snapshot = dataset_export.export_dataset_snapshot(
            job["project_id"], data_root, database
        )
        if not snapshot["exported"]:
            training_jobs.fail_training_job(database, job_id, DATASET_NOT_READY)
            print(f"Training worker stopped because job {job_id} has no valid dataset.", flush=True)
            return 1
        if training_jobs.training_job_status(database, job_id) != "running":
            print(f"Training worker stopped because job {job_id} was cancelled.", flush=True)
            return 0

        _write_job_context(run_directory, job, model_path, snapshot)
        metrics = run_ultralytics_training(
            database, job, model_path, Path(snapshot["yaml_path"]), run_directory
        )
        if training_jobs.complete_training_job(database, job_id, metrics):
            try:
                model_registry.register_completed_training_job(database, data_root, job, run_directory, metrics)
            except Exception:
                logging.exception("The completed training checkpoint could not be added to the model registry.")
            print(f"Training worker completed job {job_id}.", flush=True)
        else:
            print(f"Training worker stopped because job {job_id} was cancelled.", flush=True)
        return 0
    except Exception:
        logging.exception("The training worker failed.")
        training_jobs.fail_training_job(database, job_id, TRAINING_FAILED)
        return 1


@dataclass
class _LaunchedWorker:
    process: Any
    project_id: str


class TrainingWorkerManager:
    """The FastAPI-side launcher; it never imports or runs YOLO training itself."""

    def __init__(self, data_root: Path, database: Path):
        self.data_root = data_root
        self.database = database
        self._workers: dict[str, _LaunchedWorker] = {}
        self._lock = threading.Lock()
        self._stopping = False

    def start(self, project_id: str, job_id: str) -> training_jobs.TrainingJobResponse:
        with self._lock:
            if self._stopping:
                raise RuntimeError("The training worker manager is stopping.")
            if self._workers:
                raise AppError(
                    409,
                    "training_worker_busy",
                    "Another training job is already running. Wait for it to finish before starting this job.",
                )
            job = training_jobs.claim_training_job(self.database, project_id, job_id)
            try:
                run_directory = _job_run_directory(self.data_root, project_id, job_id)
                worker_log = _worker_output_log(self.data_root, job_id)
                environment = os.environ.copy()
                environment["VISION_STUDIO_DATA_DIR"] = str(self.data_root)
                environment["PYTHONUNBUFFERED"] = "1"
                options: dict[str, Any] = {
                    "stdin": subprocess.DEVNULL,
                    "stderr": subprocess.STDOUT,
                    "env": environment,
                    "close_fds": True,
                }
                if sys.platform == "win32":
                    options["creationflags"] = subprocess.CREATE_NO_WINDOW
                if not getattr(sys, "frozen", False):
                    options["cwd"] = str(Path(__file__).resolve().parents[1])
                with worker_log.open("ab", buffering=0) as output:
                    process = subprocess.Popen(worker_command(job_id), stdout=output, **options)
            except (OSError, RuntimeError, ValueError):
                logging.exception("The training worker process could not be started.")
                training_jobs.fail_training_job(
                    self.database,
                    job_id,
                    "The training worker could not be started. Check the application logs and try again.",
                )
                raise AppError(
                    500,
                    "training_worker_start_failed",
                    "The training worker could not be started. Check the application logs and try again.",
                ) from None
            self._workers[job_id] = _LaunchedWorker(process=process, project_id=project_id)
            threading.Thread(
                target=self._watch,
                args=(job_id, process),
                daemon=True,
                name=f"training-worker-{job_id[:8]}",
            ).start()
            return job

    def _watch(self, job_id: str, process: Any) -> None:
        try:
            process.wait()
        except Exception:
            logging.exception("The training worker process could not be observed.")
        finally:
            with self._lock:
                self._workers.pop(job_id, None)
                stopping = self._stopping
            if not stopping:
                training_jobs.fail_training_job(self.database, job_id, WORKER_EXITED)

    def shutdown(self) -> None:
        """Stop children owned by this backend before its SQLite connection disappears."""
        with self._lock:
            self._stopping = True
            workers = list(self._workers.items())
        for _, launched in workers:
            if launched.process.poll() is None:
                try:
                    launched.process.terminate()
                except OSError:
                    logging.warning("A training worker could not be terminated during backend shutdown.")
        for job_id, launched in workers:
            try:
                launched.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    launched.process.kill()
                    launched.process.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    logging.warning("A training worker could not be stopped during backend shutdown.")
            training_jobs.fail_training_job(self.database, job_id, INTERRUPTED)
