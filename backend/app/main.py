import asyncio
import os
import platform
import sys
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__, db, projects, storage, image_import, gallery, classes, annotations, dataset_export
from app.errors import register_error_handlers
from app.paths import initialize_storage


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["vision-studio-backend"] = "vision-studio-backend"
    version: str = __version__


class SystemInfoResponse(BaseModel):
    os: str
    os_version: str
    architecture: str
    cpu: str
    logical_cpu_count: int
    python_version: str
    app_version: str
    data_directory: str
    database_path: str
    database_schema_version: int
    language: Literal["en"] = "en"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data_root = initialize_storage()
    app.state.database_path = db.initialize_database(app.state.data_root)
    storage.recover_project_storage(app.state.data_root, app.state.database_path)
    gallery.cleanup_deleted_images(app.state.data_root, app.state.database_path)
    dataset_export.cleanup_pending_exports(app.state.data_root, app.state.database_path)
    app.state.image_import_slots = asyncio.Semaphore(2)
    yield


app = FastAPI(title="Vision Studio API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:1420", "http://localhost:1420",
        "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)
register_error_handlers(app)
app.include_router(projects.router)
app.include_router(image_import.router)
app.include_router(gallery.router)
app.include_router(classes.router)
app.include_router(annotations.router)
app.include_router(dataset_export.router)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.get("/system/info", response_model=SystemInfoResponse)
def system_info():
    release = platform.release()
    if platform.system() == "Windows":
        windows = sys.getwindowsversion()
        # Windows 11 retains NT version 10.0; distinguish workstation builds.
        if windows.product_type == 1 and windows.build >= 22000:
            release = "11"
    return SystemInfoResponse(
        os=platform.system(),
        os_version=release,
        architecture=platform.machine(),
        cpu=platform.processor() or platform.machine() or "Unknown processor",
        logical_cpu_count=os.cpu_count() or 1,
        python_version=platform.python_version(),
        app_version=__version__,
        data_directory=str(app.state.data_root),
        database_path=str(app.state.database_path),
        database_schema_version=db.SCHEMA_VERSION,
    )
