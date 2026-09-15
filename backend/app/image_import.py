"""Bounded image upload, original-byte storage, and oriented thumbnails."""

import hashlib
import io
import logging
import uuid
import warnings
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool
from PIL import Image, ImageOps, UnidentifiedImageError

from app import db, storage
from app.errors import AppError
from app.projects import WorkspaceDep, _now, _read

MAX_BYTES = 25 * 1024 * 1024
MAX_PIXELS = 25_000_000
THUMBNAIL_SIZE = 256
FORMATS = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}
router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["image import"])


def validate_filename(filename: str) -> str:
    if not filename or len(filename) > 255 or any(c in filename for c in ("/", "\\")) or any(ord(c) < 32 for c in filename):
        raise AppError(422, "invalid_filename", "Choose an image with a valid file name.")
    extension = Path(filename).suffix.lower()
    if extension not in FORMATS:
        raise AppError(415, "unsupported_image", "Choose a JPG, JPEG, PNG, or WEBP image.")
    return extension


def prepare_image(data: bytes, extension: str) -> tuple[int, int, bytes]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
                if source.format != FORMATS[extension]:
                    raise AppError(422, "image_format_mismatch", "The image contents do not match its file extension.")
                if source.width * source.height > MAX_PIXELS:
                    raise AppError(413, "image_dimensions_too_large", "Choose an image with no more than 25 million pixels.")
                if getattr(source, "is_animated", False):
                    raise AppError(422, "animated_image", "Animated images are not supported. Choose a still image.")
                source.verify()
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as source:
                oriented = ImageOps.exif_transpose(source)
                width, height = oriented.size
                oriented.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE), Image.Resampling.LANCZOS)
                rgba = oriented.convert("RGBA")
                thumbnail = Image.new("RGB", rgba.size, "white")
                thumbnail.paste(rgba, mask=rgba.getchannel("A"))
                output = io.BytesIO()
                thumbnail.save(output, format="JPEG", quality=85)
                return width, height, output.getvalue()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise AppError(413, "image_dimensions_too_large", "Choose an image with no more than 25 million pixels.") from error
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as error:
        raise AppError(422, "invalid_image", "This image is damaged or cannot be decoded. Choose another file.") from error


def image_path(root: Path, project_id: str, relative: str) -> Path:
    """Only database-owned paths within the reserved image folders are served."""
    project = storage.project_directory(root, project_id)
    parts = Path(relative).parts
    if len(parts) != 3 or parts[0] != "dataset" or parts[1] not in ("images", "thumbnails"):
        raise AppError(500, "invalid_image_path", "The stored image path is invalid.")
    expected = project / relative
    if expected.resolve() != expected:
        raise AppError(500, "invalid_image_path", "Image storage must not redirect to another directory.")
    return expected


def image_response(row, project_id: str) -> dict:
    return {"id": row["id"], "file_name": row["file_name"], "width": row["width"],
            "height": row["height"], "byte_size": row["byte_size"],
            "thumbnail_url": f"/projects/{project_id}/datasets/images/{row['id']}/thumbnail"}


def store_image(space, project_id: str, filename: str, data: bytes, extension: str) -> dict:
    width, height, thumbnail = prepare_image(data, extension)
    digest = hashlib.sha256(data).hexdigest()
    image_id = uuid.uuid4().hex
    original_relative = f"dataset/images/{image_id}{extension}"
    thumbnail_relative = f"dataset/thumbnails/{image_id}.jpg"
    created = []
    try:
        with db.transaction(space.database) as connection:
            _read(connection, project_id)
            dataset = connection.execute("SELECT id FROM datasets WHERE project_id = ? AND name = 'Default dataset'", (project_id,)).fetchone()
            dataset_id = dataset["id"] if dataset else uuid.uuid4().hex
            if not dataset:
                connection.execute("INSERT INTO datasets VALUES (?, ?, 'Default dataset', ?, ?)", (dataset_id, project_id, _now(), _now()))
            duplicate = connection.execute("SELECT * FROM images WHERE dataset_id = ? AND content_hash = ?", (dataset_id, digest)).fetchone()
            if duplicate:
                return {"status": "duplicate", "image": image_response(duplicate, project_id)}
            storage.create_project_directories(space.data_root, project_id)
            for relative, content in ((original_relative, data), (thumbnail_relative, thumbnail)):
                destination = image_path(space.data_root, project_id, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with destination.open("xb") as output:
                    created.append(destination)
                    output.write(content)
            connection.execute(
                "INSERT INTO images (id, dataset_id, file_name, relative_path, width, height, byte_size, content_hash, created_at, thumbnail_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (image_id, dataset_id, filename, original_relative, width, height, len(data), digest, _now(), thumbnail_relative),
            )
            connection.execute("UPDATE datasets SET updated_at = ? WHERE id = ?", (_now(), dataset_id))
            result = image_response(connection.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone(), project_id)
        return {"status": "imported", "image": result}
    except BaseException:
        # Paths were resolved under project storage before creation. Never remove
        # a source file or a pre-existing destination when rolling back an import.
        for destination in created:
            try:
                if destination.resolve() == destination:
                    destination.unlink(missing_ok=True)
            except OSError:
                logging.warning("An incomplete image import file could not be removed.", exc_info=True)
        raise


@router.post("/images")
async def upload_image(project_id: str, request: Request, space: WorkspaceDep, filename: str = Query(min_length=1, max_length=255)):
    extension = validate_filename(filename)
    async with request.app.state.image_import_slots:
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > MAX_BYTES:
                raise AppError(413, "image_too_large", "Choose an image no larger than 25 MiB.")
            data.extend(chunk)
        return await run_in_threadpool(store_image, space, project_id, filename, bytes(data), extension)


@router.get("/summary")
def import_summary(project_id: str, space: WorkspaceDep):
    with db.session(space.database) as connection:
        _read(connection, project_id)
        total = connection.execute("SELECT COUNT(*) FROM images i JOIN datasets d ON d.id = i.dataset_id WHERE d.project_id = ?", (project_id,)).fetchone()[0]
    return {"image_count": total}


@router.get("/images/{image_id}/thumbnail")
def read_thumbnail(project_id: str, image_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        row = connection.execute("SELECT i.thumbnail_path FROM images i JOIN datasets d ON d.id = i.dataset_id WHERE d.project_id = ? AND i.id = ?", (project_id, image_id)).fetchone()
        if not row or not row["thumbnail_path"]:
            raise AppError(404, "thumbnail_not_found", "The image thumbnail is unavailable.")
        path = image_path(space.data_root, project_id, row["thumbnail_path"])
        if not path.is_file():
            raise AppError(404, "thumbnail_not_found", "The image thumbnail is unavailable.")
        return Response(path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600", "X-Content-Type-Options": "nosniff"})
