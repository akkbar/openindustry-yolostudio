"""Validated, immutable YOLO snapshots without a training-runtime dependency."""

import hashlib
import json
import logging
import math
import random
import shutil
import uuid
from collections import defaultdict

from fastapi import APIRouter
from PIL import Image, ImageOps

from app import db, storage
from app.errors import AppError
from app.image_import import image_path
from app.projects import WorkspaceDep, _read, _now

router = APIRouter(prefix="/projects/{project_id}/datasets", tags=["dataset export"])
SEED = 42


def inspect_dataset(connection, space, project_id, destination=None):
    """Validate and optionally materialize the same locked snapshot, one image at a time."""
    _read(connection, project_id)
    images = connection.execute("SELECT i.* FROM images i JOIN datasets d ON d.id=i.dataset_id WHERE d.project_id=? ORDER BY i.id", (project_id,)).fetchall()
    classes = connection.execute("SELECT * FROM classes WHERE project_id=? ORDER BY class_index", (project_id,)).fetchall()
    boxes = connection.execute("SELECT a.* FROM annotations a JOIN images i ON i.id=a.image_id JOIN datasets d ON d.id=i.dataset_id WHERE d.project_id=? ORDER BY a.id", (project_id,)).fetchall()
    mapping = {row['id']: index for index, row in enumerate(classes)}
    by_image = defaultdict(list)
    for box in boxes:
        by_image[box['image_id']].append(box)
    report = dict(valid=True, images=len(images), annotations=len(boxes), classes=len(classes), issue_count=0, issues=[])

    def issue(code, message, image=None, box=None):
        report['valid'] = False
        report['issue_count'] += 1
        if len(report['issues']) < 200:
            report['issues'].append(dict(code=code, message=message, image_id=image['id'] if image else None, file_name=image['file_name'] if image else None, annotation_id=box['id'] if box else None))

    if len(images) < 2:
        issue('insufficient_images', 'Import at least two annotated images for separate training and validation sets.')
    if not classes:
        issue('missing_class', 'Add at least one class before exporting.')
    shuffled = [row['id'] for row in images]
    random.Random(SEED).shuffle(shuffled)
    val_count = max(1, round(len(images) * .2)) if len(images) > 1 else 0
    validation_ids = set(shuffled[:val_count])
    seen = {}
    manifest = []
    for row in images:
        split = 'val' if row['id'] in validation_ids else 'train'
        annotations = by_image[row['id']]
        if not annotations:
            issue('zero_annotation', 'This image has no annotations. Annotate it or remove it before exporting.', row)
        lines = []
        for box in annotations:
            if box['class_id'] not in mapping:
                issue('missing_class', 'This annotation references a missing or foreign class.', row, box)
                continue
            values = [box[key] for key in ('center_x', 'center_y', 'width', 'height')]
            if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values) or values[2] <= 0 or values[3] <= 0:
                issue('invalid_box', 'This box must have finite coordinates and positive dimensions.', row, box)
                continue
            x, y, w, h = values
            if min(x-w/2, y-h/2) < -1e-9 or max(x+w/2, y+h/2) > 1+1e-9:
                issue('box_outside_image', 'This box extends outside the image.', row, box)
                continue
            lines.append(f"{mapping[box['class_id']]} " + ' '.join(format(v, '.17g') for v in values))
        try:
            source = image_path(space.data_root, project_id, row['relative_path'])
            if not source.is_file():
                issue('missing_image', 'The original image file is missing.', row)
                continue
            with Image.open(source) as original:
                if original.width * original.height > 25_000_000:
                    raise ValueError('Image exceeds the supported pixel limit.')
                oriented = ImageOps.exif_transpose(original).convert('RGB')
                if oriented.size != (row['width'], row['height']):
                    issue('invalid_image', 'The image dimensions no longer match its annotations.', row)
                fingerprint = hashlib.sha256(f'{oriented.width}x{oriented.height}:'.encode())
                fingerprint.update(oriented.tobytes())
                digest = fingerprint.hexdigest()
                if digest in seen:
                    issue('duplicate_image', f"This image duplicates {seen[digest]}. Remove one copy before exporting.", row)
                seen[digest] = row['file_name']
                # Generated UUID names prevent collisions and path injection from user names.
                output_name = uuid.UUID(row['id']).hex
                if destination is not None:
                    oriented.save(destination / 'images' / split / f'{output_name}.png', 'PNG')
                    (destination / 'labels' / split / f'{output_name}.txt').write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
                manifest.append(dict(image_id=row['id'], file_name=row['file_name'], split=split, exported_name=f'{output_name}.png'))
        except (OSError, ValueError, AppError, Image.DecompressionBombError):
            if destination is not None:
                # Output failures must fail the whole snapshot, never publish partial files.
                raise AppError(409, 'export_image_failed', 'An image could not be read or written. Validate the dataset and check available disk space, then retry.')
            issue('invalid_image', 'The original image cannot be read safely.', row)
    return report, classes, manifest


def cleanup_pending_exports(root, database):
    """Discard only generated, unpublished snapshots left by a terminated process."""
    with db.transaction(database) as connection:
        for project in connection.execute('SELECT id FROM projects').fetchall():
            try:
                parent = storage.project_directory(root, project['id']) / 'dataset-export'
            except (ValueError, OSError):
                logging.warning('Dataset export cleanup skipped an invalid project storage path.')
                continue
            if parent.resolve() != parent:
                continue
            for candidate in parent.glob('.pending-*'):
                identifier = candidate.name.removeprefix('.pending-')
                if len(identifier) != 32 or any(char not in '0123456789abcdef' for char in identifier) or candidate.resolve() != candidate:
                    continue
                try:
                    shutil.rmtree(candidate)
                except OSError:
                    logging.warning('An unfinished dataset export could not be removed; cleanup will be retried on the next start.')


@router.post('/validate')
def validate_dataset(project_id: str, space: WorkspaceDep):
    with db.transaction(space.database) as connection:
        report, _, _ = inspect_dataset(connection, space, project_id)
    return report


@router.post('/export')
def export_dataset(project_id: str, space: WorkspaceDep):
    # Serialize against annotation edits, imports and deletion until all files are copied.
    with db.transaction(space.database) as connection:
        _read(connection, project_id)
        initial, _, _ = inspect_dataset(connection, space, project_id)
        if not initial['valid']:
            return dict(exported=False, validation=initial)
        parent = storage.project_directory(space.data_root, project_id) / 'dataset-export'
        if parent.resolve() != parent:
            raise AppError(409, 'export_storage_invalid', 'Export storage must not redirect to another directory.')
        parent.mkdir(exist_ok=True)
        export_id = uuid.uuid4().hex
        staging = parent / f'.pending-{export_id}'
        target = parent / export_id
        staging.mkdir()
        try:
            for category in ('images', 'labels'):
                for split in ('train', 'val'):
                    (staging / category / split).mkdir(parents=True)
            report, classes, manifest = inspect_dataset(connection, space, project_id, staging)
            if not report['valid']:
                return dict(exported=False, validation=report)
            names = {index: row['name'] for index, row in enumerate(classes)}
            # JSON strings/maps are valid YAML and safely preserve user class names.
            yaml = f'path: {json.dumps(target.as_posix())}\ntrain: images/train\nval: images/val\nnames: {json.dumps(names, ensure_ascii=False)}\n'
            (staging / 'data.yaml').write_text(yaml, encoding='utf-8')
            metadata = dict(export_id=export_id, created_at=_now(), seed=SEED, train_ratio=.8, images=manifest, classes=[dict(id=row['id'], project_index=row['class_index'], export_index=index, name=row['name']) for index, row in enumerate(classes)])
            (staging / 'manifest.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            staging.rename(target)
            return dict(exported=True, validation=report, export_id=export_id, path=str(target), yaml_path=str(target / 'data.yaml'), train_images=sum(row['split']=='train' for row in manifest), val_images=sum(row['split']=='val' for row in manifest), seed=SEED)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
