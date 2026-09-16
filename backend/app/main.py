import asyncio
import logging
import os
import platform
import sys
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app import __version__, annotations, base_models, camera_sessions, cameras, classes, counting, dataset_export, db, demo_datasets, events, gallery, image_import, model_catalog, model_registry, project_cameras, projects, storage, training_jobs, training_worker, vision_runtime
from app.errors import register_error_handlers
from app.paths import initialize_storage


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: Literal["vision-studio-backend"] = "vision-studio-backend"
    version: str = __version__


class VisionRuntimeResponse(BaseModel):
    status: Literal["ready"]
    ultralytics_version: str
    torch_version: str
    torchvision_version: str
    opencv_version: str


class BaseModelResponse(BaseModel):
    status: Literal["ready"]
    id: Literal["yolo11n"]
    display_name: Literal["YOLO11 Nano"]
    task: Literal["object_detection"]
    file_name: Literal["yolo11n.pt"]
    path: str
    byte_size: int
    sha256: str
    distribution: Literal["bundled"]
    load_verified: bool
    license: str


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
    vision_runtime: VisionRuntimeResponse
    base_model: BaseModelResponse
    language: Literal["en"] = "en"


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.data_root = initialize_storage()
    app.state.database_path = db.initialize_database(app.state.data_root)
    storage.recover_project_storage(app.state.data_root, app.state.database_path)
    gallery.cleanup_deleted_images(app.state.data_root, app.state.database_path)
    dataset_export.cleanup_pending_exports(app.state.data_root, app.state.database_path)
    interrupted = training_jobs.recover_interrupted_training_jobs(app.state.database_path)
    if interrupted:
        logging.warning("Recovered %s interrupted training job(s).", interrupted)
    app.state.vision_runtime = VisionRuntimeResponse(
        **vision_runtime.initialize_runtime(app.state.data_root)
    )
    app.state.base_model = BaseModelResponse(
        **base_models.provision_base_model(app.state.data_root)
    )
    app.state.image_import_slots = asyncio.Semaphore(2)
    app.state.training_workers = training_worker.TrainingWorkerManager(
        app.state.data_root, app.state.database_path
    )
    app.state.camera_sessions = camera_sessions.CameraSessionManager(
        app.state.data_root, app.state.database_path
    )
    app.state.demo_datasets = demo_datasets.DemoDatasetManager(
        app.state.data_root, app.state.database_path
    )
    try:
        yield
    finally:
        app.state.camera_sessions.shutdown()
        app.state.training_workers.shutdown()


app = FastAPI(title="OpenIndustry Vision Studio API", version=__version__, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:1420", "http://localhost:1420",
        "http://tauri.localhost", "https://tauri.localhost", "tauri://localhost",
    ],
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
    expose_headers=["X-Vision-Frame-Id", "X-Vision-Detections", "X-Vision-Counters", "X-Vision-ROI-Active"],
)
register_error_handlers(app)
app.include_router(projects.router)
app.include_router(image_import.router)
app.include_router(gallery.router)
app.include_router(classes.router)
app.include_router(annotations.router)
app.include_router(dataset_export.router)
app.include_router(training_jobs.router)
app.include_router(model_registry.router)
app.include_router(model_catalog.router)
app.include_router(counting.router)
app.include_router(cameras.router)
app.include_router(project_cameras.router)
app.include_router(camera_sessions.router)
app.include_router(camera_sessions.rtsp_router)
app.include_router(events.router)
app.include_router(demo_datasets.router)


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse()


@app.get("/models/base", response_model=BaseModelResponse)
def base_model():
    return app.state.base_model


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
        vision_runtime=app.state.vision_runtime,
        base_model=app.state.base_model,
    )
