"""Project-scoped registry for completed local training artifacts."""

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import db, storage
from app.errors import AppError
from app.projects import WorkspaceDep, _now, _read


ModelStatus = Literal["development", "production", "archived"]
router = APIRouter(prefix="/projects/{project_id}/models", tags=["models"])


class RegisteredModelResponse(BaseModel):
    id: str
    project_id: str
    training_job_id: str | None
    name: str
    version: int
    status: ModelStatus
    path: str
    dataset_export_id: str | None
    settings: dict[str, object]
    metrics: dict[str, float]
    created_at: str
    active: bool


class ModelListResponse(BaseModel):
    models: list[RegisteredModelResponse]
    active_model_id: str | None


class ModelRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a model name")
        return value


def _read_model(connection, project_id: str, model_id: str):
    row = connection.execute(
        "SELECT * FROM models WHERE id = ? AND project_id = ?", (model_id, project_id)
    ).fetchone()
    if row is None:
        raise AppError(404, "model_not_found", "This trained model is no longer available in the project.")
    return row


def _model_path(data_root: Path, project_id: str, relative_path: str | None) -> Path:
    if not relative_path:
        raise AppError(409, "model_artifact_missing", "This trained model does not have a saved checkpoint.")
    project = storage.project_directory(data_root, project_id)
    candidate = (project / relative_path).resolve()
    if candidate.parent != (project / "models").resolve() or candidate.suffix != ".pt":
        raise AppError(500, "model_path_invalid", "The trained model path is invalid. Check the application logs and try again.")
    return candidate


def _response(row, data_root: Path, active_model_id: str | None) -> RegisteredModelResponse:
    return RegisteredModelResponse(
        id=row["id"], project_id=row["project_id"], training_job_id=row["training_job_id"],
        name=row["name"], version=row["version"], status=row["status"],
        path=str(_model_path(data_root, row["project_id"], row["relative_path"])),
        dataset_export_id=row["dataset_export_id"],
        settings=json.loads(row["settings"] or "{}"), metrics=json.loads(row["metrics"] or "{}"),
        created_at=row["created_at"], active=row["id"] == active_model_id,
    )


def _context_export_id(run_directory: Path) -> str | None:
    try:
        context = json.loads((run_directory / "training-context.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    export_id = context.get("dataset_export_id")
    return export_id if isinstance(export_id, str) else None


def register_completed_training_job(database: Path, data_root: Path, job: dict, run_directory: Path, metrics: dict[str, float]) -> str | None:
    """Copy Ultralytics' best checkpoint into a project registry entry once."""
    source = run_directory / "weights" / "best.pt"
    if not source.is_file():
        return None
    model_id = uuid.uuid4().hex
    destination = storage.project_directory(data_root, job["project_id"]) / "models" / f"{model_id}.pt"
    temporary = destination.with_suffix(".tmp")
    try:
        shutil.copyfile(source, temporary)
        os.replace(temporary, destination)
        with db.transaction(database) as connection:
            project = _read(connection, job["project_id"])
            existing = connection.execute(
                "SELECT id FROM models WHERE training_job_id = ?", (job["id"],)
            ).fetchone()
            if existing is not None:
                destination.unlink(missing_ok=True)
                return existing["id"]
            completed = connection.execute(
                "SELECT status FROM training_jobs WHERE id = ?", (job["id"],)
            ).fetchone()
            if completed is None or completed["status"] != "completed":
                destination.unlink(missing_ok=True)
                return None
            version = connection.execute(
                "SELECT COALESCE(MAX(version), 0) + 1 FROM models WHERE project_id = ?",
                (job["project_id"],),
            ).fetchone()[0]
            settings = {"model": job["model"], "epochs": job["epochs"], "imgsz": job["imgsz"], "device": job["device"]}
            connection.execute(
                "INSERT INTO models (id, project_id, training_job_id, name, version, status, relative_path, metrics, created_at, dataset_export_id, settings) "
                "VALUES (?, ?, ?, ?, ?, 'development', ?, ?, ?, ?, ?)",
                (model_id, job["project_id"], job["id"], f"{project['name']} v{version}", version,
                 f"models/{model_id}.pt", json.dumps(metrics, allow_nan=False, separators=(",", ":")),
                 _now(), _context_export_id(run_directory), json.dumps(settings, separators=(",", ":"))),
            )
        return model_id
    except Exception:
        temporary.unlink(missing_ok=True)
        destination.unlink(missing_ok=True)
        raise


@router.get("", response_model=ModelListResponse)
def list_models(project_id: str, space: WorkspaceDep) -> ModelListResponse:
    with db.transaction(space.database) as connection:
        project = _read(connection, project_id)
        rows = connection.execute(
            "SELECT * FROM models WHERE project_id = ? ORDER BY version DESC, created_at DESC", (project_id,)
        ).fetchall()
        return ModelListResponse(models=[_response(row, space.data_root, project["active_model_id"]) for row in rows], active_model_id=project["active_model_id"])


@router.patch("/{model_id}", response_model=RegisteredModelResponse)
def rename_model(project_id: str, model_id: str, payload: ModelRenameRequest, space: WorkspaceDep) -> RegisteredModelResponse:
    with db.transaction(space.database) as connection:
        project = _read(connection, project_id)
        _read_model(connection, project_id, model_id)
        connection.execute("UPDATE models SET name = ? WHERE id = ?", (payload.name, model_id))
        return _response(_read_model(connection, project_id, model_id), space.data_root, project["active_model_id"])


@router.post("/{model_id}/activate", response_model=RegisteredModelResponse)
def activate_model(project_id: str, model_id: str, space: WorkspaceDep) -> RegisteredModelResponse:
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        _read_model(connection, project_id, model_id)
        connection.execute("UPDATE models SET status = 'development' WHERE project_id = ? AND status = 'production' AND id != ?", (project_id, model_id))
        connection.execute("UPDATE models SET status = 'production' WHERE id = ?", (model_id,))
        connection.execute("UPDATE projects SET active_model_id = ?, updated_at = ? WHERE id = ?", (model_id, _now(), project_id))
        return _response(_read_model(connection, project_id, model_id), space.data_root, model_id)


@router.post("/{model_id}/archive", response_model=RegisteredModelResponse)
def archive_model(project_id: str, model_id: str, space: WorkspaceDep) -> RegisteredModelResponse:
    with db.transaction(space.database) as connection:
        project = _read(connection, project_id)
        _read_model(connection, project_id, model_id)
        active = project["active_model_id"]
        connection.execute("UPDATE models SET status = 'archived' WHERE id = ?", (model_id,))
        if active == model_id:
            connection.execute("UPDATE projects SET active_model_id = NULL, updated_at = ? WHERE id = ?", (_now(), project_id))
            active = None
        return _response(_read_model(connection, project_id, model_id), space.data_root, active)
