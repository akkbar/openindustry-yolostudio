from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.paths import data_root


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", str(tmp_path / "VisionStudio"))
    with TestClient(app) as client:
        yield client


def test_health_and_system_contract(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "vision-studio-backend", "version": "0.1.0"}
    info = client.get("/system/info").json()
    assert info["language"] == "en"
    assert info["logical_cpu_count"] >= 1
    assert info["os"] and info["cpu"] and info["python_version"]
    for directory in ("data", "projects", "logs"):
        assert (Path(info["data_directory"]) / directory).is_dir()


@pytest.mark.parametrize("origin", ["http://127.0.0.1:1420", "http://tauri.localhost", "https://tauri.localhost"])
def test_allowed_frontend_origins(client, origin):
    response = client.get("/health", headers={"Origin": origin})
    assert response.headers["access-control-allow-origin"] == origin


def test_untrusted_origin_is_not_allowed(client):
    response = client.get("/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_relative_data_override_rejected(monkeypatch):
    monkeypatch.setenv("VISION_STUDIO_DATA_DIR", "data")
    with pytest.raises(ValueError, match="absolute path"):
        data_root()
