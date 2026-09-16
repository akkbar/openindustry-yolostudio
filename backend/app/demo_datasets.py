"""Download and import the built-in public Apple detector demonstration dataset."""

import hashlib
import logging
import math
import threading
import urllib.request
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app import db, image_import, storage
from app.errors import AppError
from app.projects import _name_key, _now

SOURCE_ID = "applebbch76-v1"
SOURCE_NAME = "AppleBBCH76"
SOURCE_URL = "https://www.kaggle.com/datasets/projectlzp201910094/applebbch76"
DOWNLOAD_URL = "https://www.kaggle.com/api/v1/datasets/download/projectlzp201910094/applebbch76?datasetVersionNumber=1"
SOURCE_LICENSE = "CC BY 4.0"
EXPECTED_IMAGES = 3169
EXPECTED_ARCHIVE_BYTES = 243970799
MAX_ARCHIVE_BYTES = 300 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 400 * 1024 * 1024
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

router = APIRouter(prefix="/demo-datasets", tags=["demo datasets"])


class DemoDatasetResponse(BaseModel):
    id: Literal["apple"] = "apple"
    name: str = "Apple detector demo"
    source_name: str = SOURCE_NAME
    source_url: str = SOURCE_URL
    license: str = SOURCE_LICENSE
    image_count: int = EXPECTED_IMAGES
    class_name: str = "apple"
    archive_bytes: int = Field(ge=0)
    status: Literal["not_started", "downloading", "importing", "completed", "failed"]
    progress: float = Field(ge=0, le=1)
    message: str
    project_id: str | None = None
    error: str | None = None


@dataclass
class _Job:
    status: Literal["downloading", "importing", "completed", "failed"] = "downloading"
    progress: float = 0.0
    message: str = "Preparing the Apple detector demo download."
    project_id: str | None = None
    error: str | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def update(self, *, status: Literal["downloading", "importing", "completed", "failed"] | None = None,
               progress: float | None = None, message: str | None = None,
               project_id: str | None = None, error: str | None = None) -> None:
        with self.lock:
            if status is not None:
                self.status = status
            if progress is not None:
                self.progress = max(0.0, min(1.0, progress))
            if message is not None:
                self.message = message
            if project_id is not None:
                self.project_id = project_id
            if error is not None:
                self.error = error

    def snapshot(self) -> DemoDatasetResponse:
        with self.lock:
            return DemoDatasetResponse(
                image_count=EXPECTED_IMAGES, archive_bytes=EXPECTED_ARCHIVE_BYTES, status=self.status, progress=self.progress,
                message=self.message, project_id=self.project_id, error=self.error,
            )


def demo_archive_path(root: Path) -> Path:
    return root / "demo-datasets" / f"{SOURCE_ID}.zip"


def _validate_member_name(name: str) -> Path:
    path = Path(name)
    if path.is_absolute() or ".." in path.parts or path.name != name.split("/")[-1]:
        raise AppError(422, "demo_dataset_archive_invalid", "The Apple detector archive contains an unsafe file path.")
    return path


def _parse_yolo_labels(data: bytes) -> list[tuple[float, float, float, float]]:
    try:
        lines = data.decode("utf-8").splitlines()
    except UnicodeDecodeError as error:
        raise AppError(422, "demo_dataset_labels_invalid", "The Apple detector archive contains a label file that is not UTF-8 text.") from error
    boxes: list[tuple[float, float, float, float]] = []
    for line_number, line in enumerate(lines, 1):
        parts = line.split()
        if len(parts) != 5:
            raise AppError(422, "demo_dataset_labels_invalid", f"The Apple detector archive has an invalid YOLO label at line {line_number}.")
        try:
            class_index = int(parts[0])
            center_x, center_y, width, height = (float(value) for value in parts[1:])
        except ValueError as error:
            raise AppError(422, "demo_dataset_labels_invalid", f"The Apple detector archive has a non-numeric YOLO label at line {line_number}.") from error
        if class_index != 0 or not all(math.isfinite(value) for value in (center_x, center_y, width, height)) or not 0 <= width <= 1 or not 0 <= height <= 1 or not 0 <= center_x <= 1 or not 0 <= center_y <= 1:
            raise AppError(422, "demo_dataset_labels_invalid", f"The Apple detector archive has an out-of-range YOLO label at line {line_number}.")
        # AppleBBCH76 contains four exported zero-area placeholder boxes among
        # more than 42,000 annotations. They do not describe an object and are
        # invalid YOLO training targets, so omit them while retaining the
        # image's remaining valid apple boxes.
        if width == 0 or height == 0:
            continue
        if center_x - width / 2 < 0 or center_x + width / 2 > 1 or center_y - height / 2 < 0 or center_y + height / 2 > 1:
            raise AppError(422, "demo_dataset_labels_invalid", f"The Apple detector archive has a YOLO box outside its image at line {line_number}.")
        boxes.append((center_x, center_y, width, height))
    if not boxes:
        raise AppError(422, "demo_dataset_labels_invalid", "The Apple detector archive contains an image without annotations.")
    return boxes


def _archive_members(source: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, zipfile.ZipInfo]]:
    infos = source.infolist()
    if sum(info.file_size for info in infos) > MAX_UNCOMPRESSED_BYTES:
        raise AppError(413, "demo_dataset_archive_too_large", "The Apple detector archive expands beyond the allowed size.")
    images: dict[str, zipfile.ZipInfo] = {}
    labels: dict[str, zipfile.ZipInfo] = {}
    for info in infos:
        if info.is_dir():
            continue
        _validate_member_name(info.filename)
        path = Path(info.filename)
        if len(path.parts) != 2:
            continue
        parent, extension = path.parts[0].lower(), path.suffix.lower()
        stem = path.stem
        if parent == "images" and extension in IMAGE_EXTENSIONS:
            if stem in images:
                raise AppError(422, "demo_dataset_archive_invalid", "The Apple detector archive has duplicate image names.")
            images[stem] = info
        elif parent == "labels" and extension == ".txt":
            if stem in labels:
                raise AppError(422, "demo_dataset_archive_invalid", "The Apple detector archive has duplicate label names.")
            labels[stem] = info
    if len(images) != EXPECTED_IMAGES:
        raise AppError(422, "demo_dataset_incomplete", f"The Apple detector archive must contain all {EXPECTED_IMAGES:,} source images.")
    if not images.keys() <= labels.keys():
        raise AppError(422, "demo_dataset_incomplete", "Every Apple detector image must have one matching YOLO label file.")
    return [(images[name], labels[name]) for name in sorted(images)]


def download_archive(root: Path, job: _Job) -> Path:
    destination = demo_archive_path(root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.stat().st_size == EXPECTED_ARCHIVE_BYTES and zipfile.is_zipfile(destination):
        return destination
    partial = destination.with_suffix(".partial")
    partial.unlink(missing_ok=True)
    try:
        request = urllib.request.Request(DOWNLOAD_URL, headers={"User-Agent": "OpenIndustry Vision Studio demo dataset importer"})
        with urllib.request.urlopen(request, timeout=60) as response, partial.open("xb") as output:
            total = int(response.headers.get("Content-Length", "0"))
            if total > MAX_ARCHIVE_BYTES or total not in (0, EXPECTED_ARCHIVE_BYTES):
                raise AppError(413, "demo_dataset_archive_too_large", "The Apple detector download is larger than expected.")
            received = 0
            while chunk := response.read(1024 * 1024):
                received += len(chunk)
                if received > MAX_ARCHIVE_BYTES:
                    raise AppError(413, "demo_dataset_archive_too_large", "The Apple detector download is larger than expected.")
                output.write(chunk)
                if total:
                    job.update(progress=received / total, message=f"Downloading the Apple detector demo ({received / 1024 / 1024:.0f} MiB of {total / 1024 / 1024:.0f} MiB).")
        if received != EXPECTED_ARCHIVE_BYTES:
            raise AppError(422, "demo_dataset_download_incomplete", "The Apple detector download did not contain the complete source archive.")
        partial.replace(destination)
        return destination
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _import_archive(root: Path, database: Path, archive: Path, job: _Job) -> str:
    project_id = uuid.uuid4().hex
    created_project = False
    try:
        with zipfile.ZipFile(archive) as source:
            pairs = _archive_members(source)
            job.update(status="importing", progress=0.0, message="Validating the Apple detector images and annotations.")
            with db.transaction(database) as connection:
                existing = connection.execute("SELECT project_id FROM demo_dataset_imports WHERE source_id = ?", (SOURCE_ID,)).fetchone()
                if existing:
                    return existing["project_id"]
                timestamp = _now()
                name = "Apple detector demo"
                if connection.execute("SELECT 1 FROM projects WHERE name_key = ?", (_name_key(name),)).fetchone():
                    raise AppError(409, "demo_project_name_taken", "A project named Apple detector demo already exists. Rename or delete it before importing the demo dataset.")
                connection.execute(
                    "INSERT INTO projects (id, name, name_key, description, task_type, created_at, updated_at) VALUES (?, ?, ?, ?, 'object_detection', ?, ?)",
                    (project_id, name, _name_key(name), "Full AppleBBCH76 dataset with original YOLO annotations (CC BY 4.0).", timestamp, timestamp),
                )
                created_project = True
                storage.create_project_directories(root, project_id)
                dataset_id = uuid.uuid4().hex
                class_id = uuid.uuid4().hex
                connection.execute("INSERT INTO datasets VALUES (?, ?, 'Default dataset', ?, ?)", (dataset_id, project_id, timestamp, timestamp))
                connection.execute("INSERT INTO classes VALUES (?, ?, 0, 'apple', '#19a98f', ?)", (class_id, project_id, timestamp))
                connection.execute("INSERT INTO project_annotation_state VALUES (?, ?, 1)", (project_id, class_id))
                for index, (image_info, label_info) in enumerate(pairs, 1):
                    data = source.read(image_info)
                    extension = Path(image_info.filename).suffix.lower()
                    if len(data) > image_import.MAX_BYTES:
                        raise AppError(413, "demo_dataset_image_too_large", "An Apple detector image is larger than the application import limit.")
                    width, height, thumbnail = image_import.prepare_image(data, extension)
                    boxes = _parse_yolo_labels(source.read(label_info))
                    image_id = uuid.uuid4().hex
                    original_relative = f"dataset/images/{image_id}{extension}"
                    thumbnail_relative = f"dataset/thumbnails/{image_id}.jpg"
                    original = image_import.image_path(root, project_id, original_relative)
                    thumbnail_path = image_import.image_path(root, project_id, thumbnail_relative)
                    original.parent.mkdir(parents=True, exist_ok=True)
                    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
                    original.write_bytes(data)
                    thumbnail_path.write_bytes(thumbnail)
                    connection.execute(
                        "INSERT INTO images (id, dataset_id, file_name, relative_path, width, height, byte_size, content_hash, annotated, created_at, thumbnail_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                        (image_id, dataset_id, Path(image_info.filename).name, original_relative, width, height, len(data), hashlib.sha256(data).hexdigest(), _now(), thumbnail_relative),
                    )
                    for center_x, center_y, box_width, box_height in boxes:
                        annotation_id = uuid.uuid4().hex
                        now = _now()
                        connection.execute("INSERT INTO annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (annotation_id, image_id, class_id, center_x, center_y, box_width, box_height, now, now))
                    if index == len(pairs) or index % 20 == 0:
                        job.update(progress=index / len(pairs), message=f"Importing Apple detector image {index:,} of {len(pairs):,}.")
                connection.execute("UPDATE datasets SET updated_at = ? WHERE id = ?", (_now(), dataset_id))
                connection.execute("INSERT INTO demo_dataset_imports VALUES (?, ?, ?, ?, ?)", (SOURCE_ID, project_id, SOURCE_URL, SOURCE_LICENSE, _now()))
        return project_id
    except BaseException:
        if created_project:
            try:
                storage.remove_project_directory(root, project_id)
            except OSError:
                logging.warning("The failed Apple detector demo import could not remove its project files.", exc_info=True)
        raise


class DemoDatasetManager:
    def __init__(self, data_root: Path, database: Path):
        self.data_root = data_root
        self.database = database
        self._lock = threading.Lock()
        self._job: _Job | None = None

    def _completed(self) -> DemoDatasetResponse | None:
        with db.session(self.database) as connection:
            row = connection.execute("SELECT project_id FROM demo_dataset_imports WHERE source_id = ?", (SOURCE_ID,)).fetchone()
        if row:
            return DemoDatasetResponse(image_count=EXPECTED_IMAGES, archive_bytes=demo_archive_path(self.data_root).stat().st_size if demo_archive_path(self.data_root).is_file() else 0, status="completed", progress=1, message="The Apple detector demo is ready.", project_id=row["project_id"])
        return None

    def snapshot(self) -> DemoDatasetResponse:
        completed = self._completed()
        if completed:
            return completed
        with self._lock:
            if self._job:
                return self._job.snapshot()
        return DemoDatasetResponse(image_count=EXPECTED_IMAGES, archive_bytes=EXPECTED_ARCHIVE_BYTES, status="not_started", progress=0, message="Download the full AppleBBCH76 source dataset and its YOLO annotations.")

    def start(self) -> DemoDatasetResponse:
        completed = self._completed()
        if completed:
            return completed
        with self._lock:
            if self._job and self._job.status in ("downloading", "importing"):
                return self._job.snapshot()
            self._job = _Job()
            thread = threading.Thread(target=self._run, args=(self._job,), name="apple-demo-import", daemon=True)
            thread.start()
            return self._job.snapshot()

    def _run(self, job: _Job) -> None:
        try:
            archive = download_archive(self.data_root, job)
            project_id = _import_archive(self.data_root, self.database, archive, job)
            job.update(status="completed", progress=1, message="The Apple detector demo is ready.", project_id=project_id)
        except AppError as error:
            job.update(status="failed", message="The Apple detector demo could not be imported.", error=error.message)
        except (OSError, urllib.error.URLError, zipfile.BadZipFile) as error:
            logging.warning("Apple detector demo import failed.", exc_info=True)
            if isinstance(error, zipfile.BadZipFile):
                demo_archive_path(self.data_root).unlink(missing_ok=True)
            job.update(status="failed", message="The Apple detector demo could not be imported.", error="Download the dataset again after checking your internet connection and available disk space.")
        except BaseException:
            logging.exception("Apple detector demo import failed unexpectedly.")
            job.update(status="failed", message="The Apple detector demo could not be imported.", error="The Apple detector demo import stopped unexpectedly. Retry the download.")


def manager(request: Request) -> DemoDatasetManager:
    return request.app.state.demo_datasets


ManagerDep = Depends(manager)


@router.get("/apple", response_model=DemoDatasetResponse)
def get_apple_demo(demo_manager: DemoDatasetManager = ManagerDep) -> DemoDatasetResponse:
    return demo_manager.snapshot()


@router.post("/apple", response_model=DemoDatasetResponse, status_code=202)
def start_apple_demo(demo_manager: DemoDatasetManager = ManagerDep) -> DemoDatasetResponse:
    return demo_manager.start()
