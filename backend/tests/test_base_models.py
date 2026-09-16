import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import base_models
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


def test_bundled_base_model_is_provisioned_and_reported(client, data_root):
    response = client.get("/models/base")
    assert response.status_code == 200
    model = response.json()
    destination = data_root / "models" / "base" / base_models.MODEL_FILE_NAME
    assert model == {
        "status": "ready",
        "id": "yolo11n",
        "display_name": "YOLO11 Nano",
        "task": "object_detection",
        "file_name": "yolo11n.pt",
        "path": str(destination),
        "byte_size": 5_613_764,
        "sha256": "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
        "distribution": "bundled",
        "load_verified": True,
        "license": "AGPL-3.0 or Enterprise",
    }
    assert destination.is_file()
    assert destination.stat().st_size == base_models.MODEL_BYTES
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == base_models.MODEL_SHA256
    assert client.get("/system/info").json()["base_model"] == model


def test_damaged_provisioned_model_is_repaired_from_the_bundled_asset(data_root):
    first = base_models.provision_base_model(data_root)
    destination = Path(first["path"])
    destination.write_bytes(b"damaged")
    repaired = base_models.provision_base_model(data_root)
    assert repaired == first
    assert base_models.is_valid_model(destination)
