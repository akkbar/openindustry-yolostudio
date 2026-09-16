"""Persist and serve local camera line-cross events and their snapshots."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import db, storage
from app.errors import AppError
from app.projects import WorkspaceDep, _now, _read


router = APIRouter(prefix="/projects/{project_id}/events", tags=["events"])


class EventResponse(BaseModel):
    id: int = Field(ge=1)
    project_id: str
    camera_id: str | None
    event_type: str
    class_name: str | None
    track_id: int | None
    confidence: float | None
    count: int | None
    snapshot_url: str | None
    occurred_at: str


class EventListResponse(BaseModel):
    events: list[EventResponse]
    total: int = Field(ge=0)


def _response(row) -> EventResponse:
    return EventResponse(
        id=row["id"], project_id=row["project_id"], camera_id=row["camera_id"],
        event_type=row["event_type"], class_name=row["class_name"], track_id=row["track_id"],
        confidence=row["confidence"], count=row["count"],
        snapshot_url=None if not row["snapshot_path"] else f"/projects/{row['project_id']}/events/{row['id']}/snapshot",
        occurred_at=row["occurred_at"],
    )


def record_line_cross(
    database: Path, data_root: Path, project_id: str, camera_id: str | None,
    class_name: str, track_id: int, confidence: float, count: int, jpeg: bytes,
) -> EventResponse:
    """Create an event first, then atomically attach its JPEG under project storage."""
    with db.transaction(database) as connection:
        _read(connection, project_id)
        cursor = connection.execute(
            "INSERT INTO events (project_id, camera_id, event_type, class_name, track_id, confidence, count, snapshot_path, occurred_at) VALUES (?, ?, 'line_cross', ?, ?, ?, ?, NULL, ?)",
            (project_id, camera_id, class_name, track_id, confidence, count, _now()),
        )
        event_id = int(cursor.lastrowid)
    destination = storage.project_directory(data_root, project_id) / "events" / f"{event_id}.jpg"
    temporary = destination.with_suffix(".tmp")
    try:
        temporary.write_bytes(jpeg)
        os.replace(temporary, destination)
        relative_path = f"events/{event_id}.jpg"
        with db.transaction(database) as connection:
            connection.execute("UPDATE events SET snapshot_path = ? WHERE id = ? AND project_id = ?", (relative_path, event_id, project_id))
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    except OSError:
        temporary.unlink(missing_ok=True)
        with db.session(database) as connection:
            row = connection.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    return _response(row)


@router.get("", response_model=EventListResponse)
def list_events(project_id: str, space: WorkspaceDep, limit: int = 50, offset: int = 0):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    with db.session(space.database) as connection:
        _read(connection, project_id)
        total = connection.execute("SELECT COUNT(*) FROM events WHERE project_id = ?", (project_id,)).fetchone()[0]
        rows = connection.execute(
            "SELECT * FROM events WHERE project_id = ? ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?",
            (project_id, limit, offset),
        ).fetchall()
    return EventListResponse(events=[_response(row) for row in rows], total=total)


@router.get("/{event_id}/snapshot")
def read_event_snapshot(project_id: str, event_id: int, space: WorkspaceDep):
    with db.session(space.database) as connection:
        _read(connection, project_id)
        row = connection.execute("SELECT snapshot_path FROM events WHERE id = ? AND project_id = ?", (event_id, project_id)).fetchone()
    if row is None:
        raise AppError(404, "event_not_found", "This event is no longer available.")
    relative_path = row["snapshot_path"]
    if not relative_path:
        raise AppError(404, "event_snapshot_not_found", "This event does not have a snapshot.")
    directory = storage.project_directory(space.data_root, project_id) / "events"
    candidate = (storage.project_directory(space.data_root, project_id) / relative_path).resolve()
    if candidate.parent != directory.resolve() or candidate.suffix.casefold() != ".jpg" or not candidate.is_file():
        raise AppError(404, "event_snapshot_not_found", "This event snapshot is no longer available.")
    return FileResponse(candidate, media_type="image/jpeg", headers={"Cache-Control": "no-store"})
