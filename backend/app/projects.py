"""Phase 6 project management.

A project is the container every later feature hangs from: datasets, classes,
annotations, models, cameras, and events. Creating one also creates its storage
folders (Phase 7); deleting one removes them.
"""

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field, field_validator

from app import db, storage
from app.errors import AppError

NAME_MAX_LENGTH = 80
DESCRIPTION_MAX_LENGTH = 500
TaskType = Literal["object_detection"]

router = APIRouter(prefix="/projects", tags=["projects"])


@dataclass(frozen=True)
class Workspace:
    """Resolved locations for the current request."""

    data_root: Path
    database: Path


def workspace(request: Request) -> Workspace:
    return Workspace(
        data_root=request.app.state.data_root,
        database=request.app.state.database_path,
    )


WorkspaceDep = Annotated[Workspace, Depends(workspace)]


def _now() -> str:
    # Gallery and annotation navigation use this as their stable creation order.
    # Millisecond precision can collide during a multi-file import, leaving the
    # UUID tie-breaker to reorder images unpredictably between pages.
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _clean_name(value: str) -> str:
    if not value.strip():
        raise ValueError("Enter a project name")
    if len(value) > NAME_MAX_LENGTH:
        raise ValueError(f"Use at most {NAME_MAX_LENGTH} characters for a project name")
    return value


def _clean_description(value: str) -> str:
    if len(value) > DESCRIPTION_MAX_LENGTH:
        raise ValueError(
            f"Use at most {DESCRIPTION_MAX_LENGTH} characters for a project description"
        )
    return value


def _name_key(value: str) -> str:
    return " ".join(value.split()).casefold()


class ProjectCreateRequest(BaseModel):
    name: str
    description: str = ""
    task_type: TaskType = "object_detection"

    _validate_name = field_validator("name")(_clean_name)
    _validate_description = field_validator("description")(_clean_description)


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, value: str | None) -> str | None:
        return None if value is None else _clean_name(value)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return None if value is None else _clean_description(value)


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    task_type: TaskType
    created_at: str
    updated_at: str
    storage_path: str


class ProjectListResponse(BaseModel):
    projects: list[ProjectResponse]
    total: int = Field(ge=0)


def _to_response(row: sqlite3.Row, data_root: Path) -> ProjectResponse:
    return ProjectResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        task_type=row["task_type"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        storage_path=str(storage.project_directory(data_root, row["id"])),
    )


def _read(connection: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise AppError(
            status.HTTP_404_NOT_FOUND,
            "project_not_found",
            "This project no longer exists. Refresh the project list.",
        )
    return row


def _name_taken() -> AppError:
    return AppError(
        status.HTTP_409_CONFLICT,
        "project_name_taken",
        "A project with this name already exists. Choose a different name.",
    )


@router.get("", response_model=ProjectListResponse)
def list_projects(space: WorkspaceDep) -> ProjectListResponse:
    with db.session(space.database) as connection:
        rows = connection.execute("SELECT * FROM projects ORDER BY name_key ASC").fetchall()
    projects = [_to_response(row, space.data_root) for row in rows]
    return ProjectListResponse(projects=projects, total=len(projects))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreateRequest, space: WorkspaceDep) -> ProjectResponse:
    project_id = uuid.uuid4().hex
    timestamp = _now()
    try:
        with db.transaction(space.database) as connection:
            connection.execute(
                "INSERT INTO projects (id, name, name_key, description, task_type,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id,
                    payload.name,
                    _name_key(payload.name),
                    payload.description,
                    payload.task_type,
                    timestamp,
                    timestamp,
                ),
            )
            # Inside the transaction: a failed folder creation rolls back the row.
            storage.create_project_directories(space.data_root, project_id)
            row = _read(connection, project_id)
            return _to_response(row, space.data_root)
    except sqlite3.IntegrityError as error:
        raise _name_taken() from error
    except OSError as error:
        storage.remove_project_directory(space.data_root, project_id)
        raise AppError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "project_storage_failed",
            "The project folder could not be created. Check that the application "
            "data folder is writable, then try again.",
        ) from error


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, space: WorkspaceDep) -> ProjectResponse:
    with db.transaction(space.database) as connection:
        row = _read(connection, project_id)
        # Serialize folder repair against concurrent project deletion.
        storage.create_project_directories(space.data_root, project_id)
    return _to_response(row, space.data_root)


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str, payload: ProjectUpdateRequest, space: WorkspaceDep
) -> ProjectResponse:
    if payload.name is None and payload.description is None:
        raise AppError(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "invalid_request",
            "Provide a new name or description to update.",
        )
    try:
        with db.transaction(space.database) as connection:
            current = _read(connection, project_id)
            name = payload.name if payload.name is not None else current["name"]
            description = (
                payload.description
                if payload.description is not None
                else current["description"]
            )
            connection.execute(
                "UPDATE projects SET name = ?, name_key = ?, description = ?,"
                " updated_at = ? WHERE id = ?",
                (name, _name_key(name), description, _now(), project_id),
            )
            return _to_response(_read(connection, project_id), space.data_root)
    except sqlite3.IntegrityError as error:
        raise _name_taken() from error


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, space: WorkspaceDep) -> Response:
    try:
        with db.transaction(space.database) as connection:
            _read(connection, project_id)
            active_training = connection.execute(
                "SELECT 1 FROM training_jobs WHERE project_id = ? AND status = 'running'",
                (project_id,),
            ).fetchone()
            if active_training:
                raise AppError(
                    status.HTTP_409_CONFLICT,
                    "project_training_active",
                    "A training job is still running. Cancel it and wait for the worker to stop before deleting this project.",
                )
            # Renaming the folder is reversible if the database commit fails.
            # A Windows lock that prevents renaming leaves the project intact.
            storage.stage_project_deletion(space.data_root, project_id)
            connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    except OSError as error:
        raise AppError(
            status.HTTP_409_CONFLICT,
            "project_storage_locked",
            "The project folder is in use or is not writable. Close programs using its files, then try again.",
        ) from error
    finally:
        storage.recover_project_storage(space.data_root, space.database)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
