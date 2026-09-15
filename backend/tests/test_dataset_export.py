import io
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from app import db
from app.dataset_export import cleanup_pending_exports
from app.image_import import image_path
from test_annotations import workspace, route, box


def annotate(client, project, definition, images):
    for image in images:
        assert client.post(route(project, image), json=box(definition)).status_code == 201


def endpoint(project, action):
    return f'/projects/{project}/datasets/{action}'


def test_export_split_labels_mapping_and_repeatability(workspace):
    client, root, project, definition, images = workspace
    # Leave a gap in stable project class indices, including YAML-special text.
    assert client.delete(f'/projects/{project}/classes/{definition}').status_code == 204
    name = 'Valve: "open" # \u96f6'
    definition = client.post(f'/projects/{project}/classes', json={'name': name}).json()['id']
    annotate(client, project, definition, images)
    snapshots = []
    for _ in range(2):
        response = client.post(endpoint(project, 'export'))
        assert response.status_code == 200, response.text
        result = response.json()
        assert result['exported'] and result['validation']['valid']
        assert (result['train_images'], result['val_images'], result['seed']) == (2, 1, 42)
        target = Path(result['path'])
        assert target.is_relative_to(root)
        yaml = Path(result['yaml_path']).read_text(encoding='utf-8')
        assert json.loads(yaml.splitlines()[0].removeprefix('path: ')) == target.as_posix()
        assert json.loads(yaml.split('names: ')[1]) == {'0': name}
        assert 'train: images/train\nval: images/val\n' in yaml
        manifest = json.loads((target / 'manifest.json').read_text(encoding='utf-8'))
        assert manifest['classes'][0]['project_index'] == 1
        assert manifest['classes'][0]['export_index'] == 0
        snapshots.append((target, manifest['images']))
        for row in manifest['images']:
            label = target / 'labels' / row['split'] / f"{row['image_id']}.txt"
            tokens = label.read_text().split()
            assert tokens[0] == '0'
            assert list(map(float, tokens[1:])) == [.5, .5, .4, .3]
            with Image.open(target / 'images' / row['split'] / row['exported_name']) as image:
                assert image.size == (640, 320)
    assert snapshots[0][0] != snapshots[1][0]
    assert snapshots[0][1] == snapshots[1][1]
    assert snapshots[0][0].is_dir()
    with db.session(db.database_path(root)) as connection:
        assert connection.execute('SELECT DISTINCT split FROM images').fetchone()[0] == 'unassigned'


@pytest.mark.parametrize('corruption,code', [
    ('zero', 'zero_annotation'), ('negative', 'invalid_box'),
    ('outside', 'box_outside_image'), ('infinite', 'invalid_box'),
    ('foreign', 'missing_class'), ('missing', 'missing_image'),
    ('corrupt', 'invalid_image'), ('dimensions', 'invalid_image'),
    ('duplicate', 'duplicate_image'), ('path', 'invalid_image'),
])
def test_validation_blocks_corrupt_dataset_without_publishing(workspace, corruption, code):
    client, root, project, definition, images = workspace
    annotate(client, project, definition, images)
    with db.transaction(db.database_path(root)) as connection:
        row = connection.execute('SELECT * FROM images WHERE id=?', (images[0],)).fetchone()
        source = image_path(root, project, row['relative_path'])
        if corruption == 'zero':
            connection.execute('DELETE FROM annotations WHERE image_id=?', (images[0],))
        elif corruption in ('negative', 'outside', 'infinite'):
            column, value = {'negative': ('width', -1), 'outside': ('center_x', 2), 'infinite': ('height', float('inf'))}[corruption]
            connection.execute(f'UPDATE annotations SET {column}=? WHERE image_id=?', (value, images[0]))
        elif corruption == 'missing': source.unlink()
        elif corruption == 'corrupt': source.write_bytes(b'not an image')
        elif corruption == 'dimensions': connection.execute('UPDATE images SET width=1 WHERE id=?', (images[0],))
        elif corruption == 'duplicate':
            other = connection.execute('SELECT * FROM images WHERE id=?', (images[1],)).fetchone()
            image_path(root, project, other['relative_path']).write_bytes(source.read_bytes())
        elif corruption == 'path': connection.execute("UPDATE images SET relative_path='../outside.png' WHERE id=?", (images[0],))
    if corruption == 'foreign':
        foreign_project = client.post('/projects', json={'name': 'Foreign'}).json()['id']
        foreign_class = client.post(f'/projects/{foreign_project}/classes', json={'name': 'Foreign'}).json()['id']
        with db.transaction(db.database_path(root)) as connection:
            connection.execute('UPDATE annotations SET class_id=? WHERE image_id=?', (foreign_class, images[0]))
    report = client.post(endpoint(project, 'validate')).json()
    assert not report['valid']
    assert code in {issue['code'] for issue in report['issues']}
    response = client.post(endpoint(project, 'export')).json()
    assert not response['exported'] and not response['validation']['valid']
    parent = root / 'projects' / project / 'dataset-export'
    assert not parent.exists() or not list(parent.iterdir())


def test_empty_single_image_and_project_isolation(workspace):
    client, _, project, definition, images = workspace
    empty = client.post('/projects', json={'name': 'Empty'}).json()['id']
    report = client.post(endpoint(empty, 'validate')).json()
    assert (report['images'], report['annotations'], report['classes']) == (0, 0, 0)
    assert {issue['code'] for issue in report['issues']} == {'insufficient_images', 'missing_class'}
    for image in images[1:]: client.delete(f'/projects/{project}/datasets/images/{image}')
    annotate(client, project, definition, images[:1])
    assert not client.post(endpoint(project, 'export')).json()['exported']
    assert client.post(endpoint('0'*32, 'validate')).status_code == 404
    assert client.post(endpoint('0'*32, 'export')).status_code == 404


def test_export_orients_exif_pixels_to_match_box_coordinates(workspace):
    client, _, project, definition, images = workspace
    output = io.BytesIO()
    original = Image.new('RGB', (80, 40), 'red')
    exif = original.getexif(); exif[274] = 6
    original.save(output, 'JPEG', exif=exif)
    oriented = client.post(f'/projects/{project}/datasets/images?filename=rotated.jpg', content=output.getvalue()).json()['image']
    assert (oriented['width'], oriented['height']) == (40, 80)
    annotate(client, project, definition, [*images, oriented['id']])
    result = client.post(endpoint(project, 'export')).json()
    target = Path(result['path'])
    exported = next((target / 'images').glob(f"*/{oriented['id']}.png"))
    with Image.open(exported) as image:
        assert image.size == (40, 80) and image.getexif().get(274, 1) == 1


def test_output_failure_cleans_partial_snapshot(workspace):
    client, root, project, definition, images = workspace
    annotate(client, project, definition, images)
    with patch('app.dataset_export.Image.Image.save', side_effect=OSError('Disk full')):
        result = client.post(endpoint(project, 'export'))
    assert result.status_code == 409
    assert not list((root / 'projects' / project / 'dataset-export').iterdir())
    assert client.post(endpoint(project, 'export')).json()['exported']


def test_startup_cleanup_preserves_published_and_unrelated_folders(workspace):
    client, root, project, definition, images = workspace
    annotate(client, project, definition, images)
    published = Path(client.post(endpoint(project, 'export')).json()['path'])
    pending = published.parent / ('.pending-' + 'a'*32)
    pending.mkdir(); (pending / 'partial.png').write_bytes(b'partial')
    unrelated = published.parent / '.pending-user-notes'
    unrelated.mkdir()
    cleanup_pending_exports(root, db.database_path(root))
    assert not pending.exists() and unrelated.is_dir() and (published / 'data.yaml').is_file()
