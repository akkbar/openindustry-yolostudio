from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.parametrize("build,product_type,release,expected", [
    (19045, 1, "10", "10"), (26200, 1, "10", "11"), (26100, 3, "2025Server", "2025Server"),
])
def test_windows_display_version(client, monkeypatch, build, product_type, release, expected):
    monkeypatch.setattr("app.main.platform.system", lambda: "Windows")
    monkeypatch.setattr("app.main.platform.release", lambda: release)
    monkeypatch.setattr("app.main.sys.getwindowsversion", lambda: SimpleNamespace(build=build, product_type=product_type), raising=False)
    assert client.get("/system/info").json()["os_version"] == expected
