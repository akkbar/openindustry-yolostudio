"""Metadata-driven shared pretrained model catalog and project selections."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app import base_models, db, storage
from app.errors import AppError
from app.projects import ProjectCreateRequest, WorkspaceDep, _now, _read, create_project

CatalogTask = Literal["detect", "pose", "segment", "classify"]
SourceType = Literal["builtin", "downloadable"]
InstallationStatus = Literal["BUILT_IN", "AVAILABLE", "DOWNLOADING", "INSTALLED", "ERROR", "UPDATE_AVAILABLE"]


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    name: str
    category: str
    description: str
    task: CatalogTask
    source_type: SourceType
    classes: tuple[str, ...]
    class_filter: tuple[str, ...] = ()
    base_model_id: str | None = None
    recommended_confidence: float = 0.4
    recommended_iou: float = 0.7
    fine_tuning_recommended: bool = False
    model_version: str = "1.0.0"
    source: str = "Ultralytics YOLO11 Nano COCO"
    source_url: str | None = "https://docs.ultralytics.com/models/yolo11/"
    author: str = "Ultralytics"
    license: str = "AGPL-3.0 or Enterprise"
    dataset_license: str = "unknown"
    redistribution_allowed: bool | None = None
    expected_filename: str | None = None
    download_url: str | None = None
    checksum: str | None = None


_COCO = "person,bicycle,car,motorcycle,airplane,bus,train,truck,boat,traffic light,fire hydrant,stop sign,parking meter,bench,bird,cat,dog,horse,sheep,cow,elephant,bear,zebra,giraffe,backpack,umbrella,handbag,tie,suitcase,frisbee,skis,snowboard,sports ball,kite,baseball bat,baseball glove,skateboard,surfboard,tennis racket,bottle,wine glass,cup,fork,knife,spoon,bowl,banana,apple,sandwich,orange,broccoli,carrot,hot dog,pizza,donut,cake,chair,couch,potted plant,bed,dining table,toilet,tv,laptop,mouse,remote,keyboard,cell phone,microwave,oven,toaster,sink,refrigerator,book,clock,vase,scissors,teddy bear,hair drier,toothbrush".split(",")


def _builtin(id: str, name: str, category: str, description: str, classes: tuple[str, ...], *, class_filter: tuple[str, ...] = (), confidence: float = 0.4, fine_tuning: bool = False) -> ModelDefinition:
    return ModelDefinition(id, name, category, description, "detect", "builtin", classes, class_filter, "yolo11n", confidence, fine_tuning_recommended=fine_tuning)


def _specialized(id: str, name: str, category: str, description: str, task: CatalogTask, classes: tuple[str, ...], *, fine_tuning: bool = False) -> ModelDefinition:
    return ModelDefinition(
        id, name, category, description, task, "downloadable", classes,
        fine_tuning_recommended=fine_tuning, source="unknown", source_url=None,
        author="unknown", license="unknown", dataset_license="unknown",
        redistribution_allowed=False, expected_filename=f"{id}.pt",
    )


CATALOG: tuple[ModelDefinition, ...] = (
    _builtin("general-coco", "General Object Detection", "General", "Detects the 80 standard COCO object classes with the bundled CPU-ready YOLO model.", tuple(_COCO), confidence=0.25),
    _builtin("person-detection", "Person Detection", "General", "Person-only detection preset using the shared general COCO weights.", ("person",), class_filter=("person",), confidence=0.35),
    _builtin("vehicle-detection", "Vehicle Detection", "General", "Detects cars, trucks, buses, and motorcycles using the shared general COCO weights.", ("car", "truck", "bus", "motorcycle"), class_filter=("car", "truck", "bus", "motorcycle"), confidence=0.35),
    _builtin("fruit-detection", "Fruit Detection", "General", "Detects bananas, apples, and oranges using the shared general COCO weights.", ("banana", "apple", "orange"), class_filter=("banana", "apple", "orange"), confidence=0.35),
    _builtin("bottle-detection", "Bottle Detection", "General", "Bottle-only detection preset using the shared general COCO weights.", ("bottle",), class_filter=("bottle",), confidence=0.35),
    _builtin("person-counter", "Person Counter", "People", "Person detection preset configured as a starting point for people-counting workflows.", ("person",), class_filter=("person",), confidence=0.35),
    _builtin("vehicle-counter", "Vehicle Counter", "Logistics", "Vehicle detection preset configured as a starting point for vehicle-counting workflows.", ("car", "truck", "bus", "motorcycle"), class_filter=("car", "truck", "bus", "motorcycle"), confidence=0.35),
    _builtin("animal-detection", "Animal Detection", "General", "Detects common animals available in the shared general COCO model.", ("bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"), class_filter=("bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe")),
    _builtin("food-detection", "Food Detection", "General", "Detects common food classes available in the shared general COCO model.", ("banana", "apple", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake"), class_filter=("banana", "apple", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake")),
    _builtin("safety-zone-person", "Safety Zone Person Detection", "Safety", "Person-only starter preset for safety-zone rules and future ROI workflows.", ("person",), class_filter=("person",), confidence=0.35),
    _builtin("warehouse-object-detection", "Warehouse Object Detection", "Logistics", "General COCO detection preset for people, vehicles, bottles, backpacks, and suitcases.", ("person", "car", "truck", "bus", "bottle", "backpack", "suitcase"), class_filter=("person", "car", "truck", "bus", "bottle", "backpack", "suitcase")),
    _builtin("conveyor-product-starter", "Conveyor Product Detection", "Manufacturing", "General-purpose starter for collecting product examples on a conveyor. Fine-tune for production classes.", tuple(_COCO), fine_tuning=True),
    _builtin("defect-detection-starter", "Defect Detection Starter", "Manufacturing", "Starter preset for validating camera and workflow setup. Fine-tuning is required for defect classes.", tuple(_COCO), fine_tuning=True),
    _specialized("human-pose", "Human Pose", "People", "Body keypoint estimation. Install verified pose weights before inference.", "pose", ("person",)),
    _specialized("face-detection", "Face Detection", "People", "Face bounding-box detection only. Facial recognition is not included.", "detect", ("face",)),
    _specialized("hand-detection", "Hand Detection", "People", "Hand bounding-box detection starter for gesture applications.", "detect", ("hand",)),
    _specialized("ppe-detection", "PPE Detection", "Safety", "Detects workers, helmets, and safety vests after verified weights are installed.", "detect", ("person", "helmet", "no_helmet", "vest", "no_vest")),
    _specialized("helmet-detection", "Helmet Detection", "Safety", "Detects people, helmets, and missing helmets after verified weights are installed.", "detect", ("person", "helmet", "no_helmet")),
    _specialized("fire-smoke", "Fire and Smoke Detection", "Safety", "Detects fire and smoke after verified weights are installed.", "detect", ("fire", "smoke")),
    _specialized("person-forklift-safety", "Person + Forklift Safety", "Safety", "Detects people and forklifts after verified weights are installed.", "detect", ("person", "forklift")),
    _specialized("forklift-detection", "Forklift Detection", "Logistics", "Detects forklifts and people after verified weights are installed.", "detect", ("forklift", "person")),
    _specialized("pallet-detection", "Pallet Detection", "Logistics", "Detects pallets after verified weights are installed.", "detect", ("pallet",)),
    _specialized("carton-box-detection", "Carton / Box Detection", "Logistics", "Detects cartons and boxes after verified weights are installed.", "detect", ("carton", "cardboard box", "package box")),
    _specialized("package-detection", "Package Detection", "Logistics", "Detects parcels and packages after verified weights are installed.", "detect", ("package", "parcel", "box")),
    _specialized("license-plate-detection", "License Plate Detection", "Logistics", "Detects license-plate bounding boxes. OCR is not included.", "detect", ("license plate",)),
    _specialized("can-detection", "Can Detection", "Manufacturing", "Detects cans after verified weights are installed.", "detect", ("can",)),
    _specialized("instance-segmentation", "Instance Segmentation", "Manufacturing", "Instance segmentation starter. Install verified segmentation weights before inference.", "segment", ("object",)),
)

def validate_catalog(catalog: tuple[ModelDefinition, ...]) -> None:
    if len({definition.id for definition in catalog}) != len(catalog):
        raise RuntimeError("Model catalog contains duplicate identifiers.")


validate_catalog(CATALOG)
_BY_ID = {definition.id: definition for definition in CATALOG}

router = APIRouter(prefix="/model-catalog", tags=["model catalog"])


class CatalogSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_id: str = Field(min_length=1, max_length=80)
    confidence: float | None = Field(default=None, ge=0.01, le=1)
    iou_threshold: float | None = Field(default=None, ge=0.01, le=1)


def definition(model_id: str) -> ModelDefinition:
    result = _BY_ID.get(model_id)
    if result is None:
        raise AppError(404, "catalog_model_not_found", "This pretrained model is no longer available in the model library.")
    return result


def _installation(connection, model_id: str):
    return connection.execute("SELECT * FROM catalog_model_installations WHERE model_id = ?", (model_id,)).fetchone()


def _status(connection, item: ModelDefinition) -> tuple[InstallationStatus, str | None]:
    if item.source_type == "builtin":
        return "BUILT_IN", None
    installed = _installation(connection, item.id)
    if installed is None:
        return "AVAILABLE", None
    return installed["status"], installed["error"]


def response(connection, item: ModelDefinition) -> dict:
    status, error = _status(connection, item)
    return {**asdict(item), "classes": list(item.classes), "class_filter": list(item.class_filter), "status": status, "install_error": error}


def runtime_model(connection, data_root: Path, model_id: str) -> tuple[Path, tuple[str, ...], float]:
    item = definition(model_id)
    status, _ = _status(connection, item)
    if item.source_type == "builtin" and item.base_model_id == base_models.MODEL_ID:
        return base_models.model_path(data_root), item.class_filter, item.recommended_confidence
    if status != "INSTALLED":
        raise AppError(409, "catalog_model_not_installed", "Install this pretrained model before starting inference.")
    installed = _installation(connection, item.id)
    if installed is None or not installed["relative_path"]:
        raise AppError(409, "catalog_model_artifact_missing", "The installed pretrained model file is unavailable. Install it again before starting inference.")
    candidate = (data_root / installed["relative_path"]).resolve()
    library_root = (data_root / "models" / "downloaded").resolve()
    if candidate.parent != library_root or candidate.suffix.lower() not in {".pt", ".onnx"} or not candidate.is_file():
        raise AppError(409, "catalog_model_artifact_missing", "The installed pretrained model file is unavailable. Install it again before starting inference.")
    return candidate, item.class_filter, item.recommended_confidence


def selected_project_model(connection, project_id: str) -> tuple[ModelDefinition, dict] | None:
    project = _read(connection, project_id)
    model_id = project["catalog_model_id"]
    if not model_id:
        return None
    item = definition(model_id)
    try:
        settings = json.loads(project["catalog_model_settings"] or "{}")
    except ValueError:
        settings = {}
    return item, settings if isinstance(settings, dict) else {}


@router.get("")
def list_catalog(category: str | None = None, query: str | None = None, *, space: WorkspaceDep):
    needle = (query or "").strip().casefold()
    wanted_category = (category or "").strip().casefold()
    with db.session(space.database) as connection:
        items = [item for item in CATALOG if (not wanted_category or item.category.casefold() == wanted_category) and (not needle or needle in " ".join((item.name, item.category, item.description, *item.classes)).casefold())]
        return {"models": [response(connection, item) for item in items], "categories": sorted({item.category for item in CATALOG})}


@router.get("/models/{model_id}")
def get_catalog_model(model_id: str, space: WorkspaceDep):
    with db.session(space.database) as connection:
        return response(connection, definition(model_id))


@router.post("/models/{model_id}/install")
def install_catalog_model(model_id: str, space: WorkspaceDep):
    item = definition(model_id)
    if not item.download_url:
        raise AppError(409, "model_download_unavailable", "This catalog entry has no verified download source yet, so it cannot be installed automatically.")
    raise AppError(501, "model_install_not_implemented", "Verified model downloads are not available in this release.")


@router.get("/projects/{project_id}/selection")
def get_project_selection(project_id: str, space: WorkspaceDep):
    with db.session(space.database) as connection:
        selection = selected_project_model(connection, project_id)
        if selection is None:
            return {"model": None, "settings": None}
        item, settings = selection
        return {"model": response(connection, item), "settings": settings}


@router.put("/projects/{project_id}/selection")
def select_project_model(project_id: str, payload: CatalogSelectionRequest, space: WorkspaceDep):
    item = definition(payload.model_id)
    with db.transaction(space.database) as connection:
        project = _read(connection, project_id)
        status, _ = _status(connection, item)
        if status not in ("BUILT_IN", "INSTALLED"):
            raise AppError(409, "catalog_model_not_installed", "Install this pretrained model before using it in a project.")
        settings = {"confidence": payload.confidence if payload.confidence is not None else item.recommended_confidence, "iou_threshold": payload.iou_threshold if payload.iou_threshold is not None else item.recommended_iou, "class_filter": list(item.class_filter), "model_version": item.model_version}
        connection.execute("UPDATE models SET status = 'development' WHERE project_id = ? AND status = 'production'", (project_id,))
        connection.execute("UPDATE projects SET active_model_id = NULL, catalog_model_id = ?, catalog_model_settings = ?, updated_at = ? WHERE id = ?", (item.id, json.dumps(settings, separators=(",", ":")), _now(), project_id))
        return {"model": response(connection, item), "settings": settings, "project_id": project["id"]}


@router.delete("/projects/{project_id}/selection", status_code=204)
def clear_project_selection(project_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        connection.execute("UPDATE projects SET catalog_model_id = NULL, catalog_model_settings = NULL, updated_at = ? WHERE id = ?", (_now(), project_id))


@router.post("/models/{model_id}/projects", status_code=201)
def create_project_from_catalog(model_id: str, payload: ProjectCreateRequest, space: WorkspaceDep):
    item = definition(model_id)
    created = create_project(payload, space)
    try:
        select_project_model(created.id, CatalogSelectionRequest(model_id=item.id), space)
    except BaseException:
        # A caller can delete this newly created project through normal project management if a future install state changes between requests.
        raise
    return created
