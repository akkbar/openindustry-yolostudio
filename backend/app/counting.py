"""Persisted counting configuration and bounded ByteTrack-style local tracking."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app import db
from app.errors import AppError
from app.projects import WorkspaceDep, _now, _read

router = APIRouter(prefix="/projects/{project_id}/counting", tags=["counting"])
Direction = Literal["a_to_b", "b_to_a", "both"]


class Point(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class CountingLineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    start: Point
    end: Point
    direction: Direction = "both"
    enabled: bool = True

    @model_validator(mode="after")
    def distinct_points(self):
        if self.start == self.end:
            raise ValueError("The two counting-line points must be different")
        return self


class CountingLineResponse(CountingLineRequest):
    id: str
    created_at: str
    updated_at: str


class RoiRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: list[Point] = Field(min_length=3, max_length=20)
    enabled: bool = True

    @model_validator(mode="after")
    def valid_area(self):
        area = sum(
            point.x * self.points[(index + 1) % len(self.points)].y
            - self.points[(index + 1) % len(self.points)].x * point.y
            for index, point in enumerate(self.points)
        )
        if abs(area) < 0.0001:
            raise ValueError("The ROI points must enclose an area")
        return self


class RoiResponse(RoiRequest):
    updated_at: str


class CountingConfigurationResponse(BaseModel):
    lines: list[CountingLineResponse]
    roi: RoiResponse | None


@dataclass(frozen=True)
class LineConfig:
    id: str
    name: str
    start: tuple[float, float]
    end: tuple[float, float]
    direction: Direction
    enabled: bool


@dataclass(frozen=True)
class RoiConfig:
    points: tuple[tuple[float, float], ...]
    enabled: bool


@dataclass(frozen=True)
class CountingConfiguration:
    lines: tuple[LineConfig, ...]
    roi: RoiConfig | None


def _line_response(row) -> CountingLineResponse:
    return CountingLineResponse(
        id=row["id"], name=row["name"],
        start=Point(x=row["start_x"], y=row["start_y"]), end=Point(x=row["end_x"], y=row["end_y"]),
        direction=row["direction"], enabled=bool(row["enabled"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def _roi_response(row) -> RoiResponse:
    try:
        raw_points = json.loads(row["points"])
        points = [Point.model_validate(point) for point in raw_points]
    except (ValueError, TypeError):
        raise AppError(500, "counting_config_invalid", "The saved counting configuration could not be read.")
    return RoiResponse(points=points, enabled=bool(row["enabled"]), updated_at=row["updated_at"])


def configuration(connection, project_id: str) -> CountingConfiguration:
    _read(connection, project_id)
    lines = connection.execute(
        "SELECT * FROM counting_lines WHERE project_id = ? ORDER BY created_at, id", (project_id,)
    ).fetchall()
    roi = connection.execute("SELECT * FROM project_rois WHERE project_id = ?", (project_id,)).fetchone()
    return CountingConfiguration(
        lines=tuple(
            LineConfig(row["id"], row["name"], (row["start_x"], row["start_y"]), (row["end_x"], row["end_y"]), row["direction"], bool(row["enabled"]))
            for row in lines
        ),
        roi=None if roi is None else RoiConfig(tuple((point.x, point.y) for point in _roi_response(roi).points), bool(roi["enabled"])),
    )


@router.get("", response_model=CountingConfigurationResponse)
def get_counting_configuration(project_id: str, space: WorkspaceDep):
    with db.session(space.database) as connection:
        _read(connection, project_id)
        lines = connection.execute("SELECT * FROM counting_lines WHERE project_id = ? ORDER BY created_at, id", (project_id,)).fetchall()
        roi = connection.execute("SELECT * FROM project_rois WHERE project_id = ?", (project_id,)).fetchone()
        return CountingConfigurationResponse(lines=[_line_response(line) for line in lines], roi=None if roi is None else _roi_response(roi))


@router.post("/lines", response_model=CountingLineResponse, status_code=201)
def create_counting_line(project_id: str, payload: CountingLineRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        line_id = __import__("uuid").uuid4().hex
        now = _now()
        connection.execute(
            "INSERT INTO counting_lines (id, project_id, name, start_x, start_y, end_x, end_y, direction, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (line_id, project_id, payload.name, payload.start.x, payload.start.y, payload.end.x, payload.end.y, payload.direction, int(payload.enabled), now, now),
        )
        return _line_response(connection.execute("SELECT * FROM counting_lines WHERE id = ?", (line_id,)).fetchone())


@router.patch("/lines/{line_id}", response_model=CountingLineResponse)
def update_counting_line(project_id: str, line_id: str, payload: CountingLineRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        row = connection.execute("SELECT * FROM counting_lines WHERE id = ? AND project_id = ?", (line_id, project_id)).fetchone()
        if row is None:
            raise AppError(404, "counting_line_not_found", "This counting line is no longer available.")
        now = _now()
        connection.execute(
            "UPDATE counting_lines SET name = ?, start_x = ?, start_y = ?, end_x = ?, end_y = ?, direction = ?, enabled = ?, updated_at = ? WHERE id = ?",
            (payload.name, payload.start.x, payload.start.y, payload.end.x, payload.end.y, payload.direction, int(payload.enabled), now, line_id),
        )
        return _line_response(connection.execute("SELECT * FROM counting_lines WHERE id = ?", (line_id,)).fetchone())


@router.delete("/lines/{line_id}", status_code=204)
def delete_counting_line(project_id: str, line_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        if connection.execute("DELETE FROM counting_lines WHERE id = ? AND project_id = ?", (line_id, project_id)).rowcount != 1:
            raise AppError(404, "counting_line_not_found", "This counting line is no longer available.")


@router.put("/roi", response_model=RoiResponse)
def save_roi(project_id: str, payload: RoiRequest, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        now = _now()
        connection.execute(
            "INSERT INTO project_rois (project_id, points, enabled, updated_at) VALUES (?, ?, ?, ?) ON CONFLICT(project_id) DO UPDATE SET points = excluded.points, enabled = excluded.enabled, updated_at = excluded.updated_at",
            (project_id, json.dumps([point.model_dump() for point in payload.points], separators=(",", ":")), int(payload.enabled), now),
        )
        return _roi_response(connection.execute("SELECT * FROM project_rois WHERE project_id = ?", (project_id,)).fetchone())


@router.delete("/roi", status_code=204)
def delete_roi(project_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        connection.execute("DELETE FROM project_rois WHERE project_id = ?", (project_id,))


def _iou(left: Any, right: Any) -> float:
    lx2, ly2 = left.x + left.width, left.y + left.height
    rx2, ry2 = right.x + right.width, right.y + right.height
    overlap_w = max(0.0, min(lx2, rx2) - max(left.x, right.x))
    overlap_h = max(0.0, min(ly2, ry2) - max(left.y, right.y))
    overlap = overlap_w * overlap_h
    union = left.width * left.height + right.width * right.height - overlap
    return overlap / union if union else 0.0


def _centroid(detection: Any) -> tuple[float, float]:
    return (detection.x + detection.width / 2, detection.y + detection.height / 2)


@dataclass
class _Track:
    id: int
    class_name: str
    detection: Any
    centroid: tuple[float, float]
    misses: int = 0


@dataclass(frozen=True)
class TrackedDetection:
    detection: Any
    track_id: int
    previous_centroid: tuple[float, float] | None


@dataclass(frozen=True)
class LineCrossing:
    line: LineConfig
    observation: TrackedDetection
    direction: Literal["a_to_b", "b_to_a"]
    count: int


class ByteTrackTracker:
    """A compact high/low-confidence IoU tracker for the local camera session."""

    def __init__(self, track_threshold: float = 0.25, match_iou: float = 0.25, max_misses: int = 30):
        self.track_threshold = track_threshold
        self.match_iou = match_iou
        self.max_misses = max_misses
        self._next_id = 1
        self._tracks: dict[int, _Track] = {}

    def update(self, detections: list[Any]) -> list[TrackedDetection]:
        unmatched_tracks = set(self._tracks)
        unmatched_detections = set(range(len(detections)))
        matched: dict[int, int] = {}
        for confidence_floor in (self.track_threshold, 0.0):
            choices = []
            for track_id in unmatched_tracks:
                track = self._tracks[track_id]
                for index in unmatched_detections:
                    detection = detections[index]
                    if detection.confidence >= confidence_floor and detection.class_name.casefold() == track.class_name.casefold():
                        score = _iou(track.detection, detection)
                        if score >= self.match_iou:
                            choices.append((score, track_id, index))
            for _, track_id, index in sorted(choices, reverse=True):
                if track_id in unmatched_tracks and index in unmatched_detections:
                    matched[index] = track_id
                    unmatched_tracks.remove(track_id)
                    unmatched_detections.remove(index)
        for track_id in unmatched_tracks:
            self._tracks[track_id].misses += 1
        for track_id in tuple(self._tracks):
            if self._tracks[track_id].misses > self.max_misses:
                del self._tracks[track_id]
        observations: list[TrackedDetection] = []
        for index, detection in enumerate(detections):
            track_id = matched.get(index)
            if track_id is None and detection.confidence >= self.track_threshold:
                track_id = self._next_id
                self._next_id += 1
                self._tracks[track_id] = _Track(track_id, detection.class_name, detection, _centroid(detection))
                observations.append(TrackedDetection(detection, track_id, None))
                continue
            if track_id is None:
                continue
            track = self._tracks[track_id]
            previous = track.centroid
            track.detection = detection
            track.centroid = _centroid(detection)
            track.misses = 0
            observations.append(TrackedDetection(detection, track_id, previous))
        return observations


def _inside_roi(point: tuple[float, float], roi: RoiConfig | None) -> bool:
    if roi is None or not roi.enabled:
        return True
    x, y = point
    inside = False
    for index, (left_x, left_y) in enumerate(roi.points):
        right_x, right_y = roi.points[index - 1]
        if (left_y > y) != (right_y > y) and x < (right_x - left_x) * (y - left_y) / (right_y - left_y) + left_x:
            inside = not inside
    return inside


def filter_roi(detections: list[Any], roi: RoiConfig | None) -> list[Any]:
    return [detection for detection in detections if _inside_roi(_centroid(detection), roi)]


def _side(point: tuple[float, float], line: LineConfig) -> int:
    value = (line.end[0] - line.start[0]) * (point[1] - line.start[1]) - (line.end[1] - line.start[1]) * (point[0] - line.start[0])
    return 1 if value > 0.0001 else -1 if value < -0.0001 else 0


def _crosses_segment(previous: tuple[float, float], current: tuple[float, float], line: LineConfig) -> bool:
    move = (current[0] - previous[0], current[1] - previous[1])
    vector = (line.end[0] - line.start[0], line.end[1] - line.start[1])
    denominator = move[0] * vector[1] - move[1] * vector[0]
    if abs(denominator) < 0.000001:
        return False
    relative = (line.start[0] - previous[0], line.start[1] - previous[1])
    move_t = (relative[0] * vector[1] - relative[1] * vector[0]) / denominator
    line_t = (relative[0] * move[1] - relative[1] * move[0]) / denominator
    return 0 <= move_t <= 1 and 0 <= line_t <= 1


class CrossingCounter:
    def __init__(self, lines: tuple[LineConfig, ...] = ()):
        self.lines = tuple(line for line in lines if line.enabled)
        self._sides: dict[tuple[str, int], int] = {}
        self._counted: set[tuple[str, int]] = set()
        self._counts = {line.id: {"total": 0, "a_to_b": 0, "b_to_a": 0} for line in self.lines}

    def observe(self, observations: list[TrackedDetection]) -> list[LineCrossing]:
        crossings: list[LineCrossing] = []
        for observation in observations:
            current = _centroid(observation.detection)
            for line in self.lines:
                key = (line.id, observation.track_id)
                current_side = _side(current, line)
                previous_side = self._sides.get(key)
                self._sides[key] = current_side or previous_side or 0
                if not previous_side or not current_side or previous_side == current_side or key in self._counted:
                    continue
                if observation.previous_centroid is None or not _crosses_segment(observation.previous_centroid, current, line):
                    continue
                direction: Literal["a_to_b", "b_to_a"] = "a_to_b" if previous_side < current_side else "b_to_a"
                if line.direction not in ("both", direction):
                    continue
                self._counted.add(key)
                self._counts[line.id]["total"] += 1
                self._counts[line.id][direction] += 1
                crossings.append(LineCrossing(line, observation, direction, self._counts[line.id]["total"]))
        return crossings

    def snapshot(self) -> list[dict[str, Any]]:
        return [
            {"line_id": line.id, "line_name": line.name, "count": self._counts[line.id]["total"], "a_to_b": self._counts[line.id]["a_to_b"], "b_to_a": self._counts[line.id]["b_to_a"]}
            for line in self.lines
        ]
