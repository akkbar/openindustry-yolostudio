import io
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db, image_import
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        project = client.post("/projects", json={"name": "Import test"}).json()
        yield client, root, project["id"]


def sample(format="PNG", color=(30, 80, 120), size=(640, 320), **kwargs):
    output = io.BytesIO()
    Image.new("RGB", size, color).save(output, format, **kwargs)
    return output.getvalue()


def upload(client, project, data, name="image.png"):
    return client.post(f"/projects/{project}/datasets/images", params={"filename": name}, content=data, headers={"Content-Type": "application/octet-stream"})


@pytest.mark.parametrize("format,extension", [("JPEG", "jpg"), ("JPEG", "JPEG"), ("PNG", "png"), ("WEBP", "webp")])
def test_supported_formats_copy_original_bytes_and_create_thumbnail(workspace, format, extension):
    client, root, project = workspace
    data = sample(format)
    filename = f"  Jalur gambar.{extension}"
    response = upload(client, project, data, filename)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "imported"
    assert result["image"]["file_name"] == filename
    with db.session(db.database_path(root)) as connection:
        row = connection.execute("SELECT * FROM images").fetchone()
        assert row["width"] == 640 and row["height"] == 320
        assert (root / "projects" / project / row["relative_path"]).read_bytes() == data
        assert (root / "projects" / project / row["thumbnail_path"]).is_file()
    thumb = client.get(result["image"]["thumbnail_url"])
    assert thumb.headers["content-type"] == "image/jpeg"
    with Image.open(io.BytesIO(thumb.content)) as image:
        assert image.size == (256, 128)


def test_exif_orientation_is_used_for_dimensions_and_thumbnail(workspace):
    client, _, project = workspace
    exif = Image.Exif()
    exif[274] = 6
    response = upload(client, project, sample("JPEG", exif=exif), "rotated.jpg").json()
    assert (response["image"]["width"], response["image"]["height"]) == (320, 640)
    with Image.open(io.BytesIO(client.get(response["image"]["thumbnail_url"]).content)) as thumb:
        assert thumb.size == (128, 256)


def test_imports_105_images_and_preserves_after_restart(workspace):
    client, root, project = workspace
    for index in range(105):
        response = upload(client, project, sample(color=(index, 70, 110), size=(32, 24)), f"frame-{index}.png")
        assert response.json()["status"] == "imported"
    assert client.get(f"/projects/{project}/datasets/summary").json()["image_count"] == 105
    assert len(list((root / "projects" / project / "dataset/images").iterdir())) == 105
    assert len(list((root / "projects" / project / "dataset/thumbnails").iterdir())) == 105
    with TestClient(app) as reopened:
        assert reopened.get(f"/projects/{project}/datasets/summary").json()["image_count"] == 105


def test_duplicates_are_scoped_to_project_and_names_do_not_overwrite(workspace):
    client, root, project = workspace
    data = sample()
    first = upload(client, project, data).json()
    second = upload(client, project, data, "another.png").json()
    assert second["status"] == "duplicate" and second["image"]["id"] == first["image"]["id"]
    assert upload(client, project, sample(color=(1, 2, 3))).json()["status"] == "imported"
    other = client.post("/projects", json={"name": "Other project"}).json()["id"]
    assert upload(client, other, data).json()["status"] == "imported"
    assert client.get(f"/projects/{other}/datasets/images/{first['image']['id']}/thumbnail").status_code == 404


@pytest.mark.parametrize("name,data,status", [
    ("bad.png", b"not an image", 422), ("empty.jpg", b"", 422),
    ("script.svg", b"<svg/>", 415), ("../image.png", b"bad", 422),
    ("C:\\image.jpg", b"bad", 422), ("wrong.jpg", sample(), 422),
])
def test_bad_files_do_not_create_rows_or_files(workspace, name, data, status):
    client, root, project = workspace
    response = upload(client, project, data, name)
    assert response.status_code == status
    assert "message" in response.json()["error"]
    assert client.get(f"/projects/{project}/datasets/summary").json()["image_count"] == 0
    assert list((root / "projects" / project / "dataset").iterdir()) == []


def test_byte_and_pixel_limits_are_enforced(workspace, monkeypatch):
    client, _, project = workspace
    monkeypatch.setattr(image_import, "MAX_BYTES", 100)
    assert upload(client, project, b"a" * 101).status_code == 413
    monkeypatch.setattr(image_import, "MAX_BYTES", 25 * 1024 * 1024)
    monkeypatch.setattr(image_import, "MAX_PIXELS", 100)
    assert upload(client, project, sample()).status_code == 413


def test_failed_thumbnail_write_rolls_back_files_and_database(workspace, monkeypatch):
    client, root, project = workspace
    original = Path.open
    def fail(path, mode="r", *args, **kwargs):
        if "thumbnails" in path.parts and mode == "xb":
            raise OSError("Simulated full disk")
        return original(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, "open", fail)
    assert upload(client, project, sample()).status_code == 500
    assert client.get(f"/projects/{project}/datasets/summary").json()["image_count"] == 0
    assert not list((root / "projects" / project / "dataset").rglob("*.png"))


def test_concurrent_duplicate_import_is_idempotent(workspace):
    client, root, project = workspace
    data = sample()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: upload(client, project, data).json()["status"], range(2)))
    assert sorted(results) == ["duplicate", "imported"]


def test_existing_phase_7_database_is_migrated_without_data_loss(tmp_path):
    root = tmp_path / "workspace"
    path = db.database_path(root)
    path.parent.mkdir(parents=True)
    with db.transaction(path) as connection:
        for sql in db.MIGRATIONS[0][1]:
            connection.execute(sql)
        connection.execute("PRAGMA user_version = 1")
        connection.execute("INSERT INTO projects VALUES ('p', 'Existing', 'existing', '', 'object_detection', 'now', 'now')")
    db.initialize_database(root)
    with db.session(path) as connection:
        assert connection.execute("SELECT name FROM projects").fetchone()[0] == "Existing"
        assert connection.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
        assert "thumbnail_path" in {row["name"] for row in connection.execute("PRAGMA table_info(images)")}
