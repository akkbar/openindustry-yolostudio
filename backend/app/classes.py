"""Project classes with stable indices and persisted annotation selection."""

import uuid

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, field_validator

from app import db
from app.errors import AppError
from app.projects import WorkspaceDep, _name_key, _now, _read

router = APIRouter(prefix="/projects/{project_id}", tags=["classes"])
COLORS = ("#19a98f", "#387ac5", "#b75b30", "#875bb2", "#b3467d", "#747d24")


class ClassName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str

    @field_validator("name")
    @classmethod
    def valid_name(cls, value):
        if not value.strip():
            raise ValueError("Enter a class name")
        if len(value) > 80:
            raise ValueError("Use at most 80 characters for a class name")
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("Use a class name without control characters")
        return value


class ClassSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_class_id: str | None


def ensure_state(connection, project_id):
    _read(connection, project_id)
    connection.execute("INSERT OR IGNORE INTO project_annotation_state SELECT ?, NULL, COALESCE(MAX(class_index) + 1, 0) FROM classes WHERE project_id = ?", (project_id, project_id))


def read_class(connection, project_id, class_id):
    row = connection.execute("SELECT * FROM classes WHERE project_id = ? AND id = ?", (project_id, class_id)).fetchone()
    if row is None:
        raise AppError(404, "class_not_found", "This class is no longer available in the project.")
    return row


def unique_name(connection, project_id, name, exclude=None):
    for row in connection.execute("SELECT id, name FROM classes WHERE project_id = ?", (project_id,)):
        if row["id"] != exclude and _name_key(row["name"]) == _name_key(name):
            raise AppError(409, "duplicate_class", "A class with this name already exists in the project. Choose another name.")


@router.get("/classes")
def list_classes(project_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        ensure_state(connection, project_id)
        rows = connection.execute("SELECT c.*, (SELECT COUNT(*) FROM annotations a WHERE a.class_id = c.id) AS annotation_count FROM classes c WHERE c.project_id = ? ORDER BY c.class_index", (project_id,)).fetchall()
        selected = connection.execute("SELECT selected_class_id FROM project_annotation_state WHERE project_id = ?", (project_id,)).fetchone()[0]
        return {"classes": [dict(row) for row in rows], "selected_class_id": selected}


@router.post("/classes", status_code=201)
def create_class(project_id: str, body: ClassName, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        ensure_state(connection, project_id)
        unique_name(connection, project_id, body.name)
        index = connection.execute("SELECT next_class_index FROM project_annotation_state WHERE project_id = ?", (project_id,)).fetchone()[0]
        class_id = uuid.uuid4().hex
        connection.execute("INSERT INTO classes VALUES (?, ?, ?, ?, ?, ?)", (class_id, project_id, index, body.name, COLORS[index % len(COLORS)], _now()))
        connection.execute("UPDATE project_annotation_state SET next_class_index = ?, selected_class_id = COALESCE(selected_class_id, ?) WHERE project_id = ?", (index + 1, class_id, project_id))
        return dict(read_class(connection, project_id, class_id))


@router.patch("/classes/{class_id}")
def rename_class(project_id: str, class_id: str, body: ClassName, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        ensure_state(connection, project_id)
        read_class(connection, project_id, class_id)
        unique_name(connection, project_id, body.name, class_id)
        connection.execute("UPDATE classes SET name = ? WHERE id = ?", (body.name, class_id))
        return dict(read_class(connection, project_id, class_id))


@router.delete("/classes/{class_id}", status_code=204)
def delete_class(project_id: str, class_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        ensure_state(connection, project_id)
        read_class(connection, project_id, class_id)
        if connection.execute("SELECT 1 FROM annotations WHERE class_id = ? LIMIT 1", (class_id,)).fetchone():
            raise AppError(409, "class_in_use", "This class is used by annotations. Remove or reassign those annotations before deleting the class.")
        connection.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    return Response(status_code=204)


@router.patch("/annotation-state")
def select_class(project_id: str, body: ClassSelection, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        ensure_state(connection, project_id)
        if body.selected_class_id is not None:
            read_class(connection, project_id, body.selected_class_id)
        connection.execute("UPDATE project_annotation_state SET selected_class_id = ? WHERE project_id = ?", (body.selected_class_id, project_id))
        return {"selected_class_id": body.selected_class_id}
