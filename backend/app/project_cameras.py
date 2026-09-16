"""Saved RTSP camera definitions. Passwords remain local and are never returned."""

from __future__ import annotations

import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app import db
from app.errors import AppError
from app.projects import WorkspaceDep, _now, _read


router = APIRouter(prefix="/projects/{project_id}/cameras", tags=["project cameras"])


def _clean_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() not in {"rtsp", "rtsps"} or not parsed.hostname:
        raise ValueError("Enter a valid RTSP or RTSPS camera URL")
    return value.strip()


class RtspCameraRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    url: str
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=500)

    _url = field_validator("url")(_clean_url)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Enter a camera name")
        return value.strip()


class RtspCameraUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=80)
    url: str | None = None
    username: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, max_length=500)

    _url = field_validator("url")(_clean_url)


class RtspCameraResponse(BaseModel):
    id: str
    project_id: str
    name: str
    source_type: str = "rtsp"
    url: str
    username: str | None
    has_password: bool
    created_at: str
    updated_at: str


class RtspCameraListResponse(BaseModel):
    cameras: list[RtspCameraResponse]


def _response(row) -> RtspCameraResponse:
    return RtspCameraResponse(id=row["id"], project_id=row["project_id"], name=row["name"], url=row["url"], username=row["username"], has_password=bool(row["password"]), created_at=row["created_at"], updated_at=row["updated_at"])


def read_rtsp_camera(connection, project_id: str, camera_id: str):
    row = connection.execute("SELECT * FROM cameras WHERE id = ? AND project_id = ? AND source_type = 'rtsp'", (camera_id, project_id)).fetchone()
    if row is None:
        raise AppError(404, "rtsp_camera_not_found", "This RTSP camera is no longer available.")
    return row


@router.get("/rtsp", response_model=RtspCameraListResponse)
def list_rtsp_cameras(project_id: str, space: WorkspaceDep):
    with db.session(space.database) as connection:
        _read(connection, project_id)
        rows = connection.execute("SELECT * FROM cameras WHERE project_id = ? AND source_type = 'rtsp' ORDER BY created_at, id", (project_id,)).fetchall()
    return RtspCameraListResponse(cameras=[_response(row) for row in rows])


@router.post("/rtsp", response_model=RtspCameraResponse, status_code=201)
def create_rtsp_camera(project_id: str, payload: RtspCameraRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        camera_id, now = uuid.uuid4().hex, _now()
        try:
            connection.execute("INSERT INTO cameras (id, project_id, name, source_type, url, username, password, created_at, updated_at) VALUES (?, ?, ?, 'rtsp', ?, ?, ?, ?, ?)", (camera_id, project_id, payload.name, payload.url, payload.username or None, payload.password or None, now, now))
        except Exception as error:
            if "UNIQUE constraint failed" in str(error):
                raise AppError(409, "rtsp_camera_name_exists", "A camera with this name already exists in the project.") from error
            raise
        return _response(read_rtsp_camera(connection, project_id, camera_id))


@router.patch("/rtsp/{camera_id}", response_model=RtspCameraResponse)
def update_rtsp_camera(project_id: str, camera_id: str, payload: RtspCameraUpdateRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        row = read_rtsp_camera(connection, project_id, camera_id)
        values = {
            "name": payload.name.strip() if payload.name is not None else row["name"],
            "url": payload.url if payload.url is not None else row["url"],
            "username": payload.username if payload.username is not None else row["username"],
            "password": payload.password if payload.password is not None else row["password"],
        }
        connection.execute("UPDATE cameras SET name = ?, url = ?, username = ?, password = ?, updated_at = ? WHERE id = ?", (values["name"], values["url"], values["username"] or None, values["password"] or None, _now(), camera_id))
        return _response(read_rtsp_camera(connection, project_id, camera_id))


@router.delete("/rtsp/{camera_id}", status_code=204)
def delete_rtsp_camera(project_id: str, camera_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        if connection.execute("DELETE FROM cameras WHERE id = ? AND project_id = ? AND source_type = 'rtsp'", (camera_id, project_id)).rowcount != 1:
            raise AppError(404, "rtsp_camera_not_found", "This RTSP camera is no longer available.")
