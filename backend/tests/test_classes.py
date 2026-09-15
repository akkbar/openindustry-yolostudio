from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app import db
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        project = client.post("/projects", json={"name": "Classes QA"}).json()["id"]
        yield client, root, project


def add(client, project, name):
    return client.post(f"/projects/{project}/classes", json={"name": name})


def test_create_rename_select_restart_and_stable_indices(workspace):
    client, _, project = workspace
    route = f"/projects/{project}/classes"
    assert client.get(route).json() == {"classes": [], "selected_class_id": None}
    first = add(client, project, "  Banana \u65e5\u672c  ").json()
    second = add(client, project, "Pallet").json()
    assert (first["class_index"], second["class_index"]) == (0, 1)
    assert first["name"] == "  Banana \u65e5\u672c  "
    assert client.get(route).json()["selected_class_id"] == first["id"]
    renamed = client.patch(f"{route}/{first['id']}", json={"name": "  Renamed  "}).json()
    assert (renamed["id"], renamed["class_index"], renamed["color"]) == (first["id"], 0, first["color"])
    assert client.patch(f"/projects/{project}/annotation-state", json={"selected_class_id": second["id"]}).status_code == 200
    with TestClient(app) as reopened:
        assert reopened.get(route).json()["selected_class_id"] == second["id"]
    assert client.delete(f"{route}/{first['id']}").status_code == 204
    assert client.get(route).json()["classes"][0]["class_index"] == 1
    assert client.delete(f"{route}/{second['id']}").status_code == 204
    assert client.get(route).json()["selected_class_id"] is None
    assert add(client, project, "New class").json()["class_index"] == 2


@pytest.mark.parametrize("name", ["", " \t ", "a" * 81, "a\nb", "a\x00b", "a\x7fb"])
def test_invalid_name_has_english_error_and_does_not_consume_index(workspace, name):
    client, _, project = workspace
    result = add(client, project, name)
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "invalid_request"
    assert add(client, project, "Valid").json()["class_index"] == 0


def test_duplicate_checks_preserve_names_and_are_project_scoped(workspace):
    client, _, project = workspace
    first = add(client, project, "  My Banana  ").json()
    assert add(client, project, "my   BANANA").status_code == 409
    second = add(client, project, "Pallet").json()
    assert client.patch(f"/projects/{project}/classes/{second['id']}", json={"name": "MY banana"}).status_code == 409
    assert client.patch(f"/projects/{project}/classes/{first['id']}", json={"name": "MY banana"}).status_code == 200
    other = client.post("/projects", json={"name": "Other"}).json()["id"]
    assert add(client, other, "MY banana").status_code == 201


def test_cross_project_selection_rename_delete_and_clear(workspace):
    client, _, project = workspace
    other = client.post("/projects", json={"name": "Other"}).json()["id"]
    item = add(client, other, "Private").json()
    assert client.patch(f"/projects/{project}/annotation-state", json={"selected_class_id": item["id"]}).status_code == 404
    assert client.patch(f"/projects/{project}/classes/{item['id']}", json={"name": "Changed"}).status_code == 404
    assert client.delete(f"/projects/{project}/classes/{item['id']}").status_code == 404
    assert client.patch(f"/projects/{other}/annotation-state", json={"selected_class_id": None}).json()["selected_class_id"] is None
    assert client.get(f"/projects/{other}/classes").json()["classes"][0]["name"] == "Private"


def test_used_class_cannot_be_deleted_and_rename_preserves_annotations(workspace):
    client, root, project = workspace
    item = add(client, project, "Banana").json()
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("INSERT INTO datasets VALUES ('d', ?, 'Dataset', 'now', 'now')", (project,))
        connection.execute("INSERT INTO images (id, dataset_id, file_name, relative_path, width, height, byte_size, created_at) VALUES ('i', 'd', 'image.png', 'dataset/images/i.png', 10, 10, 1, 'now')")
        connection.execute("INSERT INTO annotations VALUES ('a', 'i', ?, .5, .5, .2, .2, 'now', 'now')", (item["id"],))
    route = f"/projects/{project}/classes/{item['id']}"
    assert client.delete(route).json()["error"]["code"] == "class_in_use"
    assert client.patch(route, json={"name": "New banana"}).status_code == 200
    result = client.get(f"/projects/{project}/classes").json()
    assert result["classes"][0]["annotation_count"] == 1
    assert result["selected_class_id"] == item["id"]
    assert client.delete(f"/projects/{project}").status_code == 204
    with db.session(db.database_path(root)) as connection:
        for table in ("classes", "annotations", "project_annotation_state"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_parallel_creates_allocate_unique_indices_and_reject_duplicates(workspace):
    client, _, project = workspace
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda i: add(client, project, f"Class {i}"), range(12)))
    assert all(result.status_code == 201 for result in results)
    assert sorted(result.json()["class_index"] for result in results) == list(range(12))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: add(client, project, "Duplicate"), range(4)))
    assert sorted(result.status_code for result in results) == [201, 409, 409, 409]


def test_unknown_projects_and_invalid_payloads(workspace):
    client, _, project = workspace
    assert client.get("/projects/missing/classes").status_code == 404
    assert add(client, "missing", "Object").status_code == 404
    item = add(client, project, "Object").json()
    route = f"/projects/{project}/classes/{item['id']}"
    assert client.patch(route, json={}).status_code == 422
    assert client.patch(route, json={"name": None}).status_code == 422
    assert client.patch(route, json={"name": "Valid", "class_index": 9}).status_code == 422
    assert client.patch(f"/projects/{project}/annotation-state", json={}).status_code == 422


def test_phase_9_migration_preserves_legacy_indices(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    path = db.database_path(root)
    path.parent.mkdir(parents=True)
    with db.transaction(path) as connection:
        for _, statements in db.MIGRATIONS[:3]:
            for sql in statements:
                connection.execute(sql)
        connection.execute("PRAGMA user_version = 3")
        connection.execute("INSERT INTO projects VALUES ('p', 'Legacy', 'legacy', '', 'object_detection', 'now', 'now')")
        connection.execute("INSERT INTO classes VALUES ('c', 'p', 5, 'Legacy class', '#19a98f', 'now')")
    with TestClient(app) as client:
        assert client.get("/projects/p/classes").json()["classes"][0]["class_index"] == 5
        assert add(client, "p", "Next class").json()["class_index"] == 6
