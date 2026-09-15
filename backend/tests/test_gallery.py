import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db, gallery
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        project = client.post("/projects", json={"name": "Gallery QA"}).json()["id"]
        yield client, root, project


def upload(client, project, index=0, format="PNG", name=None):
    output = io.BytesIO()
    Image.new("RGB", (64, 32), (index, 90, 120)).save(output, format)
    data = output.getvalue()
    result = client.post(f"/projects/{project}/datasets/images", params={"filename": name or f"frame-{index}.{format.lower()}"}, content=data).json()
    return result["image"], data


def test_gallery_pagination_metadata_and_restart(workspace):
    client, root, project = workspace
    imported = [upload(client, project, index)[0] for index in range(105)]
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("UPDATE images SET annotated = 1 WHERE id = ?", (imported[0]["id"],))
    route = f"/projects/{project}/datasets/images"
    first = client.get(route).json()
    second = client.get(route, params={"offset": 60}).json()
    assert first["total"] == second["total"] == 105
    assert len(first["images"]) == 60 and len(second["images"]) == 45
    assert [row["id"] for row in first["images"] + second["images"]] == [row["id"] for row in imported]
    assert first["images"][0]["annotated"] is True
    assert first["images"][1]["annotated"] is False
    assert (first["images"][0]["width"], first["images"][0]["height"]) == (64, 32)
    assert client.get(route, params={"offset": 105}).json()["images"] == []
    with TestClient(app) as reopened:
        assert reopened.get(route).json() == first


@pytest.mark.parametrize("params", [{"offset": -1}, {"limit": 0}, {"limit": 101}])
def test_gallery_bounds(workspace, params):
    client, _, project = workspace
    assert client.get(f"/projects/{project}/datasets/images", params=params).status_code == 422


@pytest.mark.parametrize("format,media", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_original_exact_bytes_and_project_isolation(workspace, format, media):
    client, _, project = workspace
    image, data = upload(client, project, format=format, name=f" Gambar \u65e5\u672c.{format.lower()}")
    original = client.get(f"/projects/{project}/datasets/images/{image['id']}/original")
    assert original.content == data and original.headers["content-type"] == media
    assert original.headers["x-content-type-options"] == "nosniff"
    other = client.post("/projects", json={"name": "Other"}).json()["id"]
    assert client.get(f"/projects/{other}/datasets/images").json()["total"] == 0
    assert client.get(f"/projects/{other}/datasets/images/{image['id']}/original").status_code == 404
    assert client.delete(f"/projects/{other}/datasets/images/{image['id']}").status_code == 404
    assert client.get(f"/projects/{project}/datasets/images").json()["total"] == 1


def test_delete_removes_files_annotations_and_allows_reimport(workspace):
    client, root, project = workspace
    image, _ = upload(client, project)
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("INSERT INTO classes VALUES ('c', ?, 0, 'Object', '#ffffff', 'now')", (project,))
        connection.execute("INSERT INTO annotations VALUES ('a', ?, 'c', .5, .5, .1, .1, 'now', 'now')", (image["id"],))
    route = f"/projects/{project}/datasets/images/{image['id']}"
    assert client.delete(route).status_code == 204
    assert client.get(route + "/original").status_code == 404
    assert client.get(route + "/thumbnail").status_code == 404
    assert list((root / "projects" / project / "dataset/images").iterdir()) == []
    assert list((root / "projects" / project / "dataset/thumbnails").iterdir()) == []
    with db.session(db.database_path(root)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM pending_image_files").fetchone()[0] == 0
    assert upload(client, project)[0]["id"] != image["id"]


def test_locked_file_cleanup_is_durable_and_retried_on_start(workspace, monkeypatch):
    client, root, project = workspace
    image, _ = upload(client, project)
    unlink = Path.unlink
    def locked(path, *args, **kwargs):
        if path.name.startswith(image["id"]):
            raise PermissionError("QA lock")
        return unlink(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", locked)
        assert client.delete(f"/projects/{project}/datasets/images/{image['id']}").status_code == 204
        assert client.get(f"/projects/{project}/datasets/images").json()["total"] == 0
        with db.session(db.database_path(root)) as connection:
            assert connection.execute("SELECT COUNT(*) FROM pending_image_files").fetchone()[0] == 2
        replacement, _ = upload(client, project)
    with TestClient(app):
        pass
    with db.session(db.database_path(root)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM pending_image_files").fetchone()[0] == 0
    assert client.get(f"/projects/{project}/datasets/images/{replacement['id']}/original").status_code == 200


def test_delete_failure_rolls_back_database_and_preserves_files(workspace):
    client, root, project = workspace
    image, _ = upload(client, project)
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("CREATE TRIGGER prevent_delete BEFORE DELETE ON images BEGIN SELECT RAISE(ABORT, 'QA failure'); END")
    assert client.delete(f"/projects/{project}/datasets/images/{image['id']}").status_code == 500
    assert client.get(f"/projects/{project}/datasets/images/{image['id']}/original").status_code == 200
    with db.session(db.database_path(root)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM pending_image_files").fetchone()[0] == 0


def test_missing_original_and_invalid_paths(workspace):
    client, root, project = workspace
    image, _ = upload(client, project)
    with db.transaction(db.database_path(root)) as connection:
        relative = connection.execute("SELECT relative_path FROM images").fetchone()[0]
    (root / "projects" / project / relative).unlink()
    route = f"/projects/{project}/datasets/images/{image['id']}"
    assert client.get(route + "/original").status_code == 404
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("UPDATE images SET relative_path = '../../outside.png'")
    assert client.get(route + "/original").status_code == 500
    assert client.delete(route).status_code == 500


def test_phase_8_migration_preserves_images(workspace):
    client, root, project = workspace
    image, _ = upload(client, project)
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("ALTER TABLE images DROP COLUMN annotation_revision")
        connection.execute("DROP TABLE project_annotation_state")
        connection.execute("DROP TABLE pending_image_files")
        connection.execute("DROP INDEX idx_images_created")
        connection.execute("PRAGMA user_version = 2")
    db.initialize_database(root)
    assert client.get(f"/projects/{project}/datasets/images").json()["images"][0]["id"] == image["id"]
