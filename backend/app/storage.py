"""Per-project storage folders.

Layout under the writable data root:

    projects/{project-id}/
        dataset/
        models/
        runs/
        events/

Development paths are never hardcoded; everything resolves from
``app.paths.data_root``.
"""

import logging
import re
import shutil
from pathlib import Path

from app import db

PROJECT_DIRECTORIES = ("dataset", "models", "runs", "events")


def projects_root(root: Path) -> Path:
    return root / "projects"


def project_directory(root: Path, project_id: str) -> Path:
    """Resolve a project folder, refusing anything outside the projects root."""
    if not re.fullmatch(r"[0-9a-f]{32}", project_id):
        raise ValueError("The project identifier is invalid.")
    parent = projects_root(root)
    candidate = (parent / project_id).resolve()
    if parent.resolve() != root.resolve() / "projects" or candidate != parent.resolve() / project_id:
        raise ValueError("The project identifier does not resolve to a project folder.")
    return candidate


def create_project_directories(root: Path, project_id: str) -> Path:
    directory = project_directory(root, project_id)
    for name in PROJECT_DIRECTORIES:
        if (directory / name).resolve() != directory / name:
            raise OSError("Project storage must not redirect to another directory.")
        (directory / name).mkdir(parents=True, exist_ok=True)
    return directory


def remove_project_directory(root: Path, project_id: str) -> None:
    """Delete a project folder. Missing folders are not an error."""
    directory = project_directory(root, project_id)
    if directory.is_dir():
        shutil.rmtree(directory)


def deleted_directory(root: Path, project_id: str) -> Path:
    parent = project_directory(root, project_id).parent
    candidate = parent / f".deleted-{project_id}"
    if candidate.resolve() != candidate:
        raise OSError("Deleted project storage must not redirect to another directory.")
    return candidate


def stage_project_deletion(root: Path, project_id: str) -> None:
    directory = project_directory(root, project_id)
    staged = deleted_directory(root, project_id)
    if staged.exists():
        raise OSError("Project deletion is already pending.")
    if directory.exists():
        directory.rename(staged)


def recover_project_storage(root: Path, database: Path) -> None:
    """Restore interrupted transactions; retry cleanup of committed deletions.

    The database write lock also serializes recovery against project mutations.
    Only generated deletion folders directly within project storage are handled.
    """
    with db.transaction(database) as connection:
        for candidate in projects_root(root).glob(".deleted-*"):
            project_id = candidate.name.removeprefix(".deleted-")
            if not re.fullmatch(r"[0-9a-f]{32}", project_id):
                continue
            try:
                staged = deleted_directory(root, project_id)
                exists = connection.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone()
                if exists:
                    destination = project_directory(root, project_id)
                    if destination.exists():
                        raise OSError("Project recovery destination already exists.")
                    staged.rename(destination)
                else:
                    shutil.rmtree(staged)
            except (OSError, ValueError):
                logging.warning("Project folder cleanup or recovery is pending; it will be retried on the next start.", exc_info=True)
