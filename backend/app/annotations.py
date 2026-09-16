"""Normalized bounding-box CRUD with optimistic concurrency and safe retries."""

import math

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import db
from app.classes import read_class
from app.errors import AppError
from app.gallery import read_image
from app.image_import import image_response
from app.projects import WorkspaceDep, _now

router = APIRouter(prefix="/projects/{project_id}/datasets/images/{image_id}/annotations", tags=["annotations"])
BOX_FIELDS = ("class_id", "center_x", "center_y", "width", "height")


class BoxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    class_id: str
    center_x: float = Field(ge=0, le=1)
    center_y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def in_bounds(self):
        if self.center_x - self.width / 2 < -1e-9 or self.center_x + self.width / 2 > 1 + 1e-9 or self.center_y - self.height / 2 < -1e-9 or self.center_y + self.height / 2 > 1 + 1e-9:
            raise ValueError("Keep the entire bounding box inside the image")
        return self


class CreateBoxRequest(BoxRequest):
    # Stable client-generated ID makes retries after a lost response idempotent.
    id: str = Field(pattern=r"^[0-9a-f]{32}$")


def snapshot(connection, project_id, image_id):
    image = read_image(connection, project_id, image_id)
    rows = connection.execute("SELECT * FROM annotations WHERE image_id = ? ORDER BY created_at, rowid", (image_id,)).fetchall()
    order = (image["created_at"], image["sequence"])
    base = "FROM images i JOIN datasets d ON d.id = i.dataset_id WHERE d.project_id = ?"
    previous = connection.execute(f"SELECT i.id {base} AND (i.created_at, i.rowid) < (?, ?) ORDER BY i.created_at DESC, i.rowid DESC LIMIT 1", (project_id, *order)).fetchone()
    next_image = connection.execute(f"SELECT i.id {base} AND (i.created_at, i.rowid) > (?, ?) ORDER BY i.created_at, i.rowid LIMIT 1", (project_id, *order)).fetchone()
    counts = connection.execute(f"SELECT COUNT(*), COALESCE(SUM(i.annotated != 0), 0) {base}", (project_id,)).fetchone()
    position = connection.execute(f"SELECT COUNT(*) {base} AND (i.created_at, i.rowid) <= (?, ?)", (project_id, *order)).fetchone()[0]
    return {
        "image": {**image_response(image, project_id), "annotated": bool(image["annotated"]), "original_url": f"/projects/{project_id}/datasets/images/{image_id}/original"},
        "annotations": [dict(row) for row in rows], "revision": image["annotation_revision"],
        "previous_image_id": previous[0] if previous else None, "next_image_id": next_image[0] if next_image else None,
        "position": position, "total": counts[0], "annotated_count": counts[1],
    }


def check_revision(image, revision):
    if image["annotation_revision"] != revision:
        raise AppError(409, "annotation_conflict", "Annotations changed in another window. Reload the saved annotations before editing again.")


def touch_image(connection, image_id):
    connection.execute("UPDATE images SET annotated = EXISTS(SELECT 1 FROM annotations WHERE image_id = ?), annotation_revision = annotation_revision + 1 WHERE id = ?", (image_id, image_id))


def same_box(row, body):
    return row["class_id"] == body.class_id and all(math.isclose(row[key], getattr(body, key), abs_tol=1e-12) for key in BOX_FIELDS[1:])


@router.get("")
def list_annotations(project_id: str, image_id: str, space: WorkspaceDep):
    with db.session(space.database) as connection:
        connection.execute("BEGIN")
        return snapshot(connection, project_id, image_id)


@router.post("", status_code=201)
def create_annotation(project_id: str, image_id: str, body: CreateBoxRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        image = read_image(connection, project_id, image_id)
        read_class(connection, project_id, body.class_id)
        existing = connection.execute("SELECT * FROM annotations WHERE id = ?", (body.id,)).fetchone()
        if existing:
            if existing["image_id"] == image_id and same_box(existing, body):
                return snapshot(connection, project_id, image_id)
            raise AppError(409, "annotation_conflict", "This annotation identifier is already in use. Reload the saved annotations before editing again.")
        check_revision(image, body.expected_revision)
        now = _now()
        connection.execute("INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (body.id, image_id, body.class_id, body.center_x, body.center_y, body.width, body.height, now, now))
        touch_image(connection, image_id)
        return snapshot(connection, project_id, image_id)


@router.patch("/{annotation_id}")
def update_annotation(project_id: str, image_id: str, annotation_id: str, body: BoxRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        image = read_image(connection, project_id, image_id)
        read_class(connection, project_id, body.class_id)
        row = connection.execute("SELECT * FROM annotations WHERE image_id = ? AND id = ?", (image_id, annotation_id)).fetchone()
        if not row:
            raise AppError(404, "annotation_not_found", "This annotation is no longer available.")
        if not same_box(row, body):
            check_revision(image, body.expected_revision)
            connection.execute("UPDATE annotations SET class_id = ?, center_x = ?, center_y = ?, width = ?, height = ?, updated_at = ? WHERE id = ?", (body.class_id, body.center_x, body.center_y, body.width, body.height, _now(), annotation_id))
            touch_image(connection, image_id)
        return snapshot(connection, project_id, image_id)


@router.delete("/{annotation_id}")
def delete_annotation(project_id: str, image_id: str, annotation_id: str, space: WorkspaceDep, expected_revision: int = Query(ge=0)):
    with db.transaction(space.database) as connection:
        image = read_image(connection, project_id, image_id)
        if connection.execute("SELECT 1 FROM annotations WHERE image_id = ? AND id = ?", (image_id, annotation_id)).fetchone():
            check_revision(image, expected_revision)
            connection.execute("DELETE FROM annotations WHERE image_id = ? AND id = ?", (image_id, annotation_id))
            touch_image(connection, image_id)
        return snapshot(connection, project_id, image_id)
