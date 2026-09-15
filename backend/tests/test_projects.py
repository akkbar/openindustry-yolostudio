import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import db, storage
from app.main import app


@pytest.fixture
def data_root(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    return root


@pytest.fixture
def client(data_root):
    with TestClient(app) as client:
        yield client


def create(client, name="Banana Counter", **extra):
    response = client.post("/projects", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_database_is_created_on_first_start(client, data_root):
    path = data_root / "data" / db.DATABASE_FILE
    assert path.is_file()
    with db.session(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == db.SCHEMA_VERSION
        tables = {row["name"] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )}
    assert {
        "projects", "datasets", "images", "classes", "annotations",
        "models", "training_jobs", "cameras", "events",
    } <= tables


def test_system_info_reports_the_database(client, data_root):
    info = client.get("/system/info").json()
    assert Path(info["database_path"]) == data_root / "data" / db.DATABASE_FILE
    assert info["database_schema_version"] == db.SCHEMA_VERSION


def test_initializing_twice_keeps_existing_data(data_root):
    with TestClient(app) as first:
        project = create(first, "Carton Counter")
    with TestClient(app) as second:
        assert second.get(f"/projects/{project['id']}").json()["name"] == "Carton Counter"


def test_foreign_keys_and_cascade_are_enforced(client, data_root):
    project = create(client)
    path = db.database_path(data_root)
    with db.transaction(path) as connection:
        connection.execute(
            "INSERT INTO datasets (id, project_id, name, created_at, updated_at)"
            " VALUES ('d1', ?, 'Default', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')",
            (project["id"],),
        )
    with db.session(path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO datasets (id, project_id, name, created_at, updated_at)"
                " VALUES ('d2', 'missing', 'Orphan', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
    assert client.delete(f"/projects/{project['id']}").status_code == 204
    with db.session(path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 0


def test_project_lifecycle(client, data_root):
    project = create(client, "Banana Counter", description="Line 3")
    assert project["task_type"] == "object_detection"
    assert project["description"] == "Line 3"
    assert project["created_at"].endswith("Z")

    listing = client.get("/projects").json()
    assert listing["total"] == 1
    assert listing["projects"][0]["id"] == project["id"]

    renamed = client.patch(f"/projects/{project['id']}", json={"name": "Banana Counter v2"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Banana Counter v2"
    assert renamed.json()["description"] == "Line 3"
    assert renamed.json()["updated_at"] >= project["updated_at"]

    assert client.delete(f"/projects/{project['id']}").status_code == 204
    assert client.get("/projects").json()["total"] == 0


def test_projects_are_listed_alphabetically(client):
    for name in ("zebra line", "Apple line", "mango line"):
        create(client, name)
    names = [project["name"] for project in client.get("/projects").json()["projects"]]
    assert names == ["Apple line", "mango line", "zebra line"]


def test_creating_a_project_creates_its_storage(client, data_root):
    project = create(client)
    directory = data_root / "projects" / project["id"]
    assert Path(project["storage_path"]) == directory
    for name in storage.PROJECT_DIRECTORIES:
        assert (directory / name).is_dir()


def test_reading_a_project_repairs_missing_storage(client, data_root):
    project = create(client)
    storage.remove_project_directory(data_root, project["id"])
    assert not (data_root / "projects" / project["id"]).exists()
    assert client.get(f"/projects/{project['id']}").status_code == 200
    assert (data_root / "projects" / project["id"] / "dataset").is_dir()


def test_deleting_a_project_removes_its_storage(client, data_root):
    project = create(client)
    directory = data_root / "projects" / project["id"]
    (directory / "dataset" / "frame.jpg").write_bytes(b"binary")
    assert client.delete(f"/projects/{project['id']}").status_code == 204
    assert not directory.exists()


def test_project_identifiers_cannot_escape_the_projects_folder(client, data_root):
    response = client.get("/projects/..%2F..%2Fsecret")
    assert response.status_code in (404, 422)
    assert "error" in response.json()
    with pytest.raises(ValueError):
        storage.project_directory(data_root, "../escape")


@pytest.mark.parametrize("name", ["banana counter", "  Banana   Counter  ", "BANANA COUNTER"])
def test_duplicate_names_are_rejected_regardless_of_case_or_spacing(client, name):
    create(client, "Banana Counter")
    response = client.post("/projects", json={"name": name})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_name_taken"
    assert client.get("/projects").json()["total"] == 1


def test_renaming_onto_another_project_is_rejected(client):
    create(client, "Banana Counter")
    other = create(client, "Carton Counter")
    response = client.patch(f"/projects/{other['id']}", json={"name": "banana counter"})
    assert response.status_code == 409
    assert client.get(f"/projects/{other['id']}").json()["name"] == "Carton Counter"


def test_a_deleted_name_can_be_reused(client):
    project = create(client, "Banana Counter")
    client.delete(f"/projects/{project['id']}")
    assert create(client, "Banana Counter")["id"] != project["id"]


@pytest.mark.parametrize("payload,expected", [
    ({"name": ""}, 422),
    ({"name": "   "}, 422),
    ({"name": "x" * 81}, 422),
    ({"description": "only a description"}, 422),
    ({"name": "Valid", "description": "d" * 501}, 422),
    ({"name": "Valid", "task_type": "segmentation"}, 422),
])
def test_invalid_creation_is_rejected_in_english(client, payload, expected):
    response = client.post("/projects", json=payload)
    assert response.status_code == expected
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["message"].endswith(".")
    assert client.get("/projects").json()["total"] == 0


def test_empty_update_is_rejected(client):
    project = create(client)
    response = client.patch(f"/projects/{project['id']}", json={})
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Provide a new name or description to update."


def test_user_text_is_preserved_exactly(client):
    name = "  Banana   Counter — Jalur 3  "
    description = "  Catatan pengguna\nBaris kedua  "
    project = create(client, name, description=description)
    assert project["name"] == name
    assert project["description"] == description
    updated = client.patch(f"/projects/{project['id']}", json={"name": name + "x", "description": description + "\n"}).json()
    assert updated["name"] == name + "x"
    assert updated["description"] == description + "\n"


def test_failed_folder_creation_rolls_back_project(client, data_root, monkeypatch):
    def fail(root, project_id):
        (root / "projects" / project_id / "dataset").mkdir(parents=True)
        raise OSError("Simulated storage failure")
    monkeypatch.setattr(storage, "create_project_directories", fail)
    response = client.post("/projects", json={"name": "Broken"})
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "project_storage_failed"
    assert client.get("/projects").json()["total"] == 0
    assert list((data_root / "projects").iterdir()) == []


def test_locked_project_keeps_database_and_files(client, data_root, monkeypatch):
    project = create(client)
    directory = Path(project["storage_path"])
    sentinel = directory / "dataset" / "keep.txt"
    sentinel.write_text("Keep this data")
    def fail(*args):
        raise PermissionError("Simulated Windows file lock")
    monkeypatch.setattr(storage, "stage_project_deletion", fail)
    response = client.delete(f"/projects/{project['id']}")
    assert response.status_code == 409
    assert client.get("/projects").json()["total"] == 1
    assert sentinel.read_text() == "Keep this data"


def test_pending_deletion_cleanup_is_retried(client, data_root, monkeypatch):
    project = create(client)
    def fail(*args):
        raise PermissionError("Simulated locked file")
    with monkeypatch.context() as patch:
        patch.setattr(storage.shutil, "rmtree", fail)
        assert client.delete(f"/projects/{project['id']}").status_code == 204
    staged = storage.deleted_directory(data_root, project["id"])
    assert staged.exists()
    assert client.get("/projects").json()["total"] == 0
    storage.recover_project_storage(data_root, db.database_path(data_root))
    assert not staged.exists()


def test_interrupted_deletion_restores_live_project(client, data_root):
    project = create(client)
    storage.stage_project_deletion(data_root, project["id"])
    storage.recover_project_storage(data_root, db.database_path(data_root))
    assert Path(project["storage_path"]).is_dir()
    assert not storage.deleted_directory(data_root, project["id"]).exists()


def test_project_cascade_includes_annotated_images(client, data_root):
    project = create(client)
    with db.transaction(db.database_path(data_root)) as connection:
        connection.execute("INSERT INTO datasets VALUES ('d', ?, 'Dataset', 'now', 'now')", (project['id'],))
        connection.execute("INSERT INTO classes VALUES ('c', ?, 0, 'Object', '#19a98f', 'now')", (project['id'],))
        connection.execute("INSERT INTO images (id,dataset_id,file_name,relative_path,width,height,byte_size,created_at) VALUES ('i','d','a.jpg','a.jpg',10,10,100,'now')")
        connection.execute("INSERT INTO annotations VALUES ('a','i','c',0.5,0.5,0.2,0.2,'now','now')")
    assert client.delete(f"/projects/{project['id']}").status_code == 204
    with db.session(db.database_path(data_root)) as connection:
        assert connection.execute("SELECT COUNT(*) FROM annotations").fetchone()[0] == 0


def test_parallel_database_initialization(data_root):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        paths = list(pool.map(lambda _: db.initialize_database(data_root), range(4)))
    assert len(set(paths)) == 1


def test_real_windows_directory_lock_preserves_project(client):
    import ctypes
    import sys
    if sys.platform != "win32":
        pytest.skip("Windows file sharing semantics")
    project = create(client)
    directory = Path(project["storage_path"])
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(directory), 0x80000000, 3, None, 3, 0x02000000, None)
    assert handle != ctypes.c_void_p(-1).value, ctypes.get_last_error()
    try:
        assert client.delete(f"/projects/{project['id']}").status_code == 409
        assert directory.is_dir()
        assert client.get("/projects").json()["total"] == 1
    finally:
        kernel.CloseHandle(handle)
    assert client.delete(f"/projects/{project['id']}").status_code == 204


def test_missing_projects_return_an_english_error(client):
    for response in (
        client.get("/projects/missing"),
        client.patch("/projects/missing", json={"name": "New"}),
        client.delete("/projects/missing"),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "project_not_found"
        assert "no longer exists" in response.json()["error"]["message"]


def test_project_writes_are_allowed_from_the_desktop_origin(client):
    response = client.post(
        "/projects",
        json={"name": "Banana Counter"},
        headers={"Origin": "http://tauri.localhost"},
    )
    assert response.status_code == 201
    assert response.headers["access-control-allow-origin"] == "http://tauri.localhost"


def test_a_newer_schema_is_refused_instead_of_downgraded(data_root):
    path = db.initialize_database(data_root)
    with db.session(path) as connection:
        connection.execute(f"PRAGMA user_version = {db.SCHEMA_VERSION + 1}")
    with pytest.raises(RuntimeError, match="newer version of Vision Studio"):
        db.initialize_database(data_root)
