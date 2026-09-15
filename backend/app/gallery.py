"""Project-scoped gallery and durable cleanup of deleted image files."""

import logging
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import Response

from app import db
from app.errors import AppError
from app.image_import import image_path, image_response
from app.projects import WorkspaceDep, _now, _read

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["gallery"])


def read_image(connection, project_id, image_id):
    _read(connection, project_id)
    row = connection.execute("SELECT i.* FROM images i JOIN datasets d ON d.id = i.dataset_id WHERE d.project_id = ? AND i.id = ?", (project_id, image_id)).fetchone()
    if row is None:
        raise AppError(404, "image_not_found", "This image is no longer available in the project.")
    return row


def cleanup_deleted_images(root: Path, database: Path):
    # The queue commits with the deletion. A locked file or interrupted cleanup
    # is retried at startup or the next deletion; generated paths are never reused.
    with db.transaction(database) as connection:
        for row in connection.execute("SELECT * FROM pending_image_files").fetchall():
            try:
                image_path(root, row["project_id"], row["relative_path"]).unlink(missing_ok=True)
            except (OSError, AppError):
                logging.warning("A deleted image file could not be removed; cleanup will be retried.")
                continue
            connection.execute("DELETE FROM pending_image_files WHERE project_id = ? AND relative_path = ?", (row["project_id"], row["relative_path"]))


@router.get("/images")
def list_images(project_id: str, space: WorkspaceDep, offset: int = Query(0, ge=0), limit: int = Query(60, ge=1, le=100)):
    with db.session(space.database) as connection:
        connection.execute("BEGIN")
        _read(connection, project_id)
        total = connection.execute("SELECT COUNT(*) FROM images i JOIN datasets d ON d.id = i.dataset_id WHERE d.project_id = ?", (project_id,)).fetchone()[0]
        rows = connection.execute("SELECT i.* FROM images i JOIN datasets d ON d.id = i.dataset_id WHERE d.project_id = ? ORDER BY i.created_at, i.id LIMIT ? OFFSET ?", (project_id, limit, offset)).fetchall()
        return {"images": [{**image_response(row, project_id), "annotated": bool(row["annotated"]), "original_url": f"/projects/{project_id}/datasets/images/{row['id']}/original"} for row in rows], "total": total, "offset": offset, "limit": limit}


@router.get("/images/{image_id}/original")
def original_image(project_id: str, image_id: str, space: WorkspaceDep):
    # Copy bounded original bytes under the same lock as deletion; do not return
    # a FileResponse whose deferred read could race with file cleanup on Windows.
    with db.transaction(space.database) as connection:
        row = read_image(connection, project_id, image_id)
        path = image_path(space.data_root, project_id, row["relative_path"])
        if not path.is_file():
            raise AppError(404, "original_not_found", "The original image file is unavailable.")
        media = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(path.suffix.lower())
        if media is None:
            raise AppError(500, "invalid_image_path", "The stored image format is invalid.")
        return Response(path.read_bytes(), media_type=media, headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.delete("/images/{image_id}", status_code=204)
def delete_image(project_id: str, image_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        row = read_image(connection, project_id, image_id)
        for relative in (row["relative_path"], row["thumbnail_path"]):
            if relative:
                image_path(space.data_root, project_id, relative)
                connection.execute("INSERT INTO pending_image_files VALUES (?, ?)", (project_id, relative))
        connection.execute("DELETE FROM annotations WHERE image_id = ?", (image_id,))
        connection.execute("DELETE FROM images WHERE id = ?", (image_id,))
        connection.execute("UPDATE datasets SET updated_at = ? WHERE id = ?", (_now(), row["dataset_id"]))
    cleanup_deleted_images(space.data_root, space.database)
    return Response(status_code=204)
