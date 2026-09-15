import io
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import db
from app.main import app


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "VisionStudio"
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(root))
    with TestClient(app) as client:
        project = client.post("/projects", json={"name": "Annotation QA"}).json()["id"]
        definition = client.post(f"/projects/{project}/classes", json={"name": "Object"}).json()["id"]
        images = []
        for index in range(3):
            output = io.BytesIO()
            Image.new("RGB", (640, 320), (index, 80, 120)).save(output, "PNG")
            images.append(client.post(f"/projects/{project}/datasets/images?filename=frame-{index}.png", content=output.getvalue()).json()["image"]["id"])
        yield client, root, project, definition, images


def route(project, image):
    return f"/projects/{project}/datasets/images/{image}/annotations"


def box(definition, revision=0, **extra):
    return {"id": uuid.uuid4().hex, "class_id": definition, "center_x": .5, "center_y": .5, "width": .4, "height": .3, "expected_revision": revision, **extra}


def test_crud_normalized_values_restart_status_and_neighbors(workspace):
    client, _, project, definition, images = workspace
    url = route(project, images[1])
    initial = client.get(url).json()
    assert initial["previous_image_id"] == images[0] and initial["next_image_id"] == images[2]
    assert (initial["position"], initial["total"], initial["annotated_count"]) == (2, 3, 0)
    payload = box(definition)
    response = client.post(url, json=payload)
    assert response.status_code == 201, response.text
    state = response.json()
    assert state["revision"] == 1 and state["annotated_count"] == 1 and state["image"]["annotated"]
    changed = {key: value for key, value in payload.items() if key != "id"}
    changed.update(center_x=.4, width=.2, expected_revision=1)
    updated = client.patch(f"{url}/{payload['id']}", json=changed).json()
    assert updated["revision"] == 2
    with TestClient(app) as reopened:
        saved = reopened.get(url).json()["annotations"][0]
        assert (saved["center_x"], saved["center_y"], saved["width"], saved["height"]) == (.4, .5, .2, .3)
    assert client.delete(f"/projects/{project}/classes/{definition}").status_code == 409
    deleted = client.delete(f"{url}/{payload['id']}?expected_revision=2").json()
    assert deleted["annotations"] == [] and deleted["annotated_count"] == 0 and not deleted["image"]["annotated"]
    assert client.delete(f"/projects/{project}/classes/{definition}").status_code == 204
    assert client.get(route(project, images[0])).json()["previous_image_id"] is None
    assert client.get(route(project, images[-1])).json()["next_image_id"] is None


@pytest.mark.parametrize("invalid", [{"width": 0}, {"height": -1}, {"center_x": 1.1}, {"center_y": -.1}, {"width": 1.1}, {"center_x": .1, "width": .4}, {"center_y": .9, "height": .4}, {"class_id": "missing"}, {"expected_revision": -1}])
def test_rejects_invalid_boxes_without_partial_changes(workspace, invalid):
    client, _, project, definition, images = workspace
    url = route(project, images[0])
    result = client.post(url, json=box(definition, **invalid))
    assert result.status_code in (422, 404)
    assert client.get(url).json()["revision"] == 0
    assert client.get(url).json()["annotations"] == []


def test_cross_project_image_class_and_box_isolation(workspace):
    client, _, project, definition, images = workspace
    other = client.post("/projects", json={"name": "Other"}).json()["id"]
    foreign = client.post(f"/projects/{other}/classes", json={"name": "Foreign"}).json()["id"]
    payload = box(definition)
    url = route(project, images[0])
    assert client.post(url, json=box(foreign)).status_code == 404
    assert client.post(route(other, images[0]), json=payload).status_code == 404
    assert client.get(route(other, images[0])).status_code == 404
    assert client.post(url, json=payload).status_code == 201
    patch = {key: value for key, value in payload.items() if key != "id"}
    assert client.patch(f"{route(project, images[1])}/{payload['id']}", json=patch).status_code == 404
    assert client.get(url).json()["annotations"][0]["id"] == payload["id"]


def test_conflicts_and_response_loss_retries(workspace):
    client, _, project, definition, images = workspace
    url = route(project, images[0])
    payload = box(definition)
    first = client.post(url, json=payload).json()
    assert client.post(url, json=payload).json() == first
    assert client.post(url, json=box(definition)).status_code == 409
    changed = {key: value for key, value in payload.items() if key != "id"}
    changed.update(center_x=.4, expected_revision=1)
    second = client.patch(f"{url}/{payload['id']}", json=changed).json()
    assert client.patch(f"{url}/{payload['id']}", json=changed).json() == second
    assert client.delete(f"{url}/{payload['id']}?expected_revision=1").status_code == 409
    deleted = client.delete(f"{url}/{payload['id']}?expected_revision=2").json()
    assert client.delete(f"{url}/{payload['id']}?expected_revision=2").json() == deleted


def test_concurrent_writers_do_not_overwrite(workspace):
    client, _, project, definition, images = workspace
    url = route(project, images[0])
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: client.post(url, json=box(definition)), range(2)))
    assert sorted(response.status_code for response in results) == [201, 409]
    assert len(client.get(url).json()["annotations"]) == 1


def test_annotated_count_tracks_images_not_box_count_and_reassignment(workspace):
    client, _, project, definition, images = workspace
    url = route(project, images[0])
    first = box(definition)
    client.post(url, json=first)
    second = box(definition, 1)
    assert client.post(url, json=second).json()["annotated_count"] == 1
    other = client.post(f"/projects/{project}/classes", json={"name": "Other"}).json()["id"]
    patch = {key: value for key, value in second.items() if key != "id"}
    patch.update(class_id=other, expected_revision=2)
    assert client.patch(f"{url}/{second['id']}", json=patch).json()["annotations"][1]["class_id"] == other
    assert client.post(route(project, images[1]), json=box(definition)).json()["annotated_count"] == 2
    assert client.delete(f"/projects/{project}/datasets/images/{images[0]}").status_code == 204
    assert client.get(route(project, images[1])).json()["annotated_count"] == 1


def test_phase_10_migration_keeps_existing_boxes(workspace):
    client, root, project, definition, images = workspace
    url = route(project, images[0])
    payload = box(definition)
    client.post(url, json=payload)
    with db.transaction(db.database_path(root)) as connection:
        connection.execute("ALTER TABLE images DROP COLUMN annotation_revision")
        connection.execute("PRAGMA user_version = 4")
    db.initialize_database(root)
    result = client.get(url).json()
    assert result["revision"] == 0 and result["annotations"][0]["id"] == payload["id"]
