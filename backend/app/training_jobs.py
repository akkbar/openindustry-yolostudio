"""Durable training-job records and the small API used to launch a worker."""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app import db
from app.errors import AppError
from app.projects import WorkspaceDep, _now, _read


JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
router = APIRouter(prefix="/projects/{project_id}/training-jobs", tags=["training jobs"])


class TrainingJobCreate(BaseModel):
    """The deliberately small configuration accepted before the training UI exists."""

    model_config = ConfigDict(extra="forbid")

    model: Literal["yolo11n"] = "yolo11n"
    epochs: int = Field(default=50, ge=1, le=10_000)
    imgsz: int = Field(default=640, ge=32, le=4_096)


class TrainingJobResponse(BaseModel):
    id: str
    project_id: str
    status: JobStatus
    model: Literal["yolo11n"]
    epochs: int
    imgsz: int
    device: Literal["auto"]
    progress: float
    metrics: dict[str, float] | None
    created_at: str
    updated_at: str
    started_at: str | None
    finished_at: str | None
    error: str | None


class TrainingJobListResponse(BaseModel):
    jobs: list[TrainingJobResponse]
    total: int
    offset: int
    limit: int


def _read_job(connection, project_id: str, job_id: str):
    row = connection.execute(
        "SELECT * FROM training_jobs WHERE project_id = ? AND id = ?",
        (project_id, job_id),
    ).fetchone()
    if row is None:
        raise AppError(404, "training_job_not_found", "This training job is no longer available in the project.")
    return row


def _response(row) -> TrainingJobResponse:
    metrics = json.loads(row["metrics"]) if row["metrics"] is not None else None
    return TrainingJobResponse(
        id=row["id"],
        project_id=row["project_id"],
        status=row["status"],
        model=row["model"],
        epochs=row["epochs"],
        imgsz=row["imgsz"],
        device=row["device"],
        progress=row["progress"],
        metrics=metrics,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        error=row["error"],
    )


def claim_training_job(database, project_id: str, job_id: str) -> TrainingJobResponse:
    """Atomically move one queued job to running before a child is launched."""
    with db.transaction(database) as connection:
        _read(connection, project_id)
        job = _read_job(connection, project_id, job_id)
        if job["status"] == "running":
            raise AppError(
                409,
                "training_job_already_running",
                "This training job is already running.",
            )
        if job["status"] != "queued":
            raise AppError(
                409,
                "training_job_not_startable",
                "This training job can only be started while queued.",
            )
        now = _now()
        connection.execute(
            "UPDATE training_jobs SET status = 'running', started_at = ?, finished_at = NULL, "
            "error = NULL, updated_at = ? WHERE id = ?",
            (now, now, job_id),
        )
        return _response(_read_job(connection, project_id, job_id))


def read_running_training_job(database, job_id: str) -> dict | None:
    """Read worker configuration only while its job still owns execution."""
    with db.session(database) as connection:
        row = connection.execute(
            "SELECT * FROM training_jobs WHERE id = ? AND status = 'running'", (job_id,)
        ).fetchone()
    return dict(row) if row is not None else None


def training_job_status(database, job_id: str) -> str | None:
    with db.session(database) as connection:
        row = connection.execute(
            "SELECT status FROM training_jobs WHERE id = ?", (job_id,)
        ).fetchone()
    return row["status"] if row is not None else None


def update_training_job_progress(
    database, job_id: str, progress: float, metrics: dict[str, float]
) -> bool:
    """Persist a bounded worker checkpoint without reviving a cancelled job."""
    progress = min(0.99, max(0.0, float(progress)))
    now = _now()
    with db.transaction(database) as connection:
        if metrics:
            result = connection.execute(
                "UPDATE training_jobs SET progress = ?, metrics = ?, updated_at = ? "
                "WHERE id = ? AND status = 'running'",
                (
                    progress,
                    json.dumps(metrics, allow_nan=False, separators=(",", ":")),
                    now,
                    job_id,
                ),
            )
        else:
            result = connection.execute(
                "UPDATE training_jobs SET progress = ?, updated_at = ? "
                "WHERE id = ? AND status = 'running'",
                (progress, now, job_id),
            )
    return result.rowcount == 1


def complete_training_job(database, job_id: str, metrics: dict[str, float]) -> bool:
    now = _now()
    with db.transaction(database) as connection:
        result = connection.execute(
            "UPDATE training_jobs SET status = 'completed', progress = 1, metrics = ?, "
            "finished_at = ?, error = NULL, updated_at = ? "
            "WHERE id = ? AND status = 'running'",
            (json.dumps(metrics, allow_nan=False, separators=(",", ":")), now, now, job_id),
        )
    return result.rowcount == 1


def fail_training_job(database, job_id: str, message: str) -> bool:
    """Record an internal worker failure without replacing a cancellation."""
    now = _now()
    with db.transaction(database) as connection:
        result = connection.execute(
            "UPDATE training_jobs SET status = 'failed', finished_at = ?, error = ?, "
            "updated_at = ? WHERE id = ? AND status = 'running'",
            (now, message, now, job_id),
        )
    return result.rowcount == 1


def recover_interrupted_training_jobs(database) -> int:
    """Make jobs left running by a stopped backend explicit and retryable."""
    now = _now()
    with db.transaction(database) as connection:
        result = connection.execute(
            "UPDATE training_jobs SET status = 'failed', finished_at = ?, error = ?, "
            "updated_at = ? WHERE status = 'running'",
            (
                now,
                "Training was interrupted when the local backend stopped. Create a new job to retry.",
                now,
            ),
        )
    return result.rowcount


@router.get("", response_model=TrainingJobListResponse)
def list_training_jobs(
    project_id: str,
    space: WorkspaceDep,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=30, ge=1, le=100),
) -> TrainingJobListResponse:
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        total = connection.execute(
            "SELECT COUNT(*) FROM training_jobs WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        rows = connection.execute(
            "SELECT * FROM training_jobs WHERE project_id = ? "
            "ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
        return TrainingJobListResponse(
            jobs=[_response(row) for row in rows], total=total, offset=offset, limit=limit
        )


@router.post("", response_model=TrainingJobResponse, status_code=201)
def create_training_job(
    project_id: str, payload: TrainingJobCreate, space: WorkspaceDep
) -> TrainingJobResponse:
    """Queue a durable job record until the caller explicitly starts it."""
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        job_id = uuid.uuid4().hex
        created_at = _now()
        connection.execute(
            "INSERT INTO training_jobs "
            "(id, project_id, status, model, epochs, imgsz, device, progress, metrics, error, "
            "created_at, updated_at, started_at, finished_at) "
            "VALUES (?, ?, 'queued', ?, ?, ?, 'auto', 0, NULL, NULL, ?, ?, NULL, NULL)",
            (job_id, project_id, payload.model, payload.epochs, payload.imgsz, created_at, created_at),
        )
        return _response(_read_job(connection, project_id, job_id))


@router.get("/{job_id}", response_model=TrainingJobResponse)
def get_training_job(
    project_id: str, job_id: str, space: WorkspaceDep
) -> TrainingJobResponse:
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        return _response(_read_job(connection, project_id, job_id))


@router.post(
    "/{job_id}/start",
    response_model=TrainingJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_training_job(project_id: str, job_id: str, request: Request) -> TrainingJobResponse:
    """Launch the claimed job in a separate process without blocking this request."""
    return request.app.state.training_workers.start(project_id, job_id)


@router.post("/{job_id}/cancel", response_model=TrainingJobResponse)
def cancel_training_job(
    project_id: str, job_id: str, space: WorkspaceDep
) -> TrainingJobResponse:
    """Persist cancellation now; a running worker observes it between batches."""
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        job = _read_job(connection, project_id, job_id)
        if job["status"] in ("completed", "failed"):
            raise AppError(
                409,
                "training_job_not_cancellable",
                "This training job has already finished and cannot be cancelled.",
            )
        if job["status"] != "cancelled":
            now = _now()
            connection.execute(
                "UPDATE training_jobs SET status = 'cancelled', finished_at = COALESCE(finished_at, ?), "
                "updated_at = ? WHERE id = ?",
                (now, now, job_id),
            )
        return _response(_read_job(connection, project_id, job_id))
