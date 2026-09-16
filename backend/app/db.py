"""Local SQLite database for Vision Studio.

The standard library ``sqlite3`` module is used deliberately. It adds no
dependency to ``requirements-build.lock`` and is already covered by the
PyInstaller bundle, so Phase 5 does not weaken the packaging gates proven in
Phases 1-3.
"""

import sqlite3
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DATABASE_FILE = "visionstudio.db"

Migration = tuple[int, tuple[str, ...] | Callable[[sqlite3.Connection], None]]


def _migrate_training_jobs_phase_17(connection: sqlite3.Connection) -> None:
    """Name the predeclared job columns for the public Phase 17 contract.

    Earlier migration tests deliberately rewind only the schema pieces they
    exercise. Check the live columns so their already-upgraded job table is
    not renamed a second time when that simulated version is reopened.
    """
    columns = {
        row["name"] for row in connection.execute("PRAGMA table_info(training_jobs)")
    }
    if "base_model" in columns:
        connection.execute("ALTER TABLE training_jobs RENAME COLUMN base_model TO model")
    if "image_size" in columns:
        connection.execute("ALTER TABLE training_jobs RENAME COLUMN image_size TO imgsz")
    if "updated_at" not in columns:
        connection.execute("ALTER TABLE training_jobs ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
    connection.execute("UPDATE training_jobs SET updated_at = created_at WHERE updated_at = ''")
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_training_jobs_project_created "
        "ON training_jobs(project_id, created_at DESC, id DESC)"
    )


# Each entry upgrades the database from ``version - 1`` to ``version``.
# Never edit a released migration; append a new one instead.
MIGRATIONS: list[Migration] = [
    (
        1,
        (
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                name_key TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                task_type TEXT NOT NULL CHECK (task_type IN ('object_detection')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE datasets (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (project_id, name)
            )
            """,
            """
            CREATE TABLE classes (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                class_index INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT NOT NULL DEFAULT '#19a98f',
                created_at TEXT NOT NULL,
                UNIQUE (project_id, class_index),
                UNIQUE (project_id, name)
            )
            """,
            """
            CREATE TABLE images (
                id TEXT PRIMARY KEY,
                dataset_id TEXT NOT NULL REFERENCES datasets(id) ON DELETE CASCADE,
                file_name TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                byte_size INTEGER NOT NULL,
                content_hash TEXT,
                split TEXT NOT NULL DEFAULT 'unassigned'
                    CHECK (split IN ('unassigned', 'train', 'val')),
                annotated INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                UNIQUE (dataset_id, relative_path)
            )
            """,
            """
            CREATE TABLE annotations (
                id TEXT PRIMARY KEY,
                image_id TEXT NOT NULL REFERENCES images(id) ON DELETE CASCADE,
                class_id TEXT NOT NULL REFERENCES classes(id) DEFERRABLE INITIALLY DEFERRED,
                center_x REAL NOT NULL,
                center_y REAL NOT NULL,
                width REAL NOT NULL,
                height REAL NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """,
            """
            CREATE TABLE training_jobs (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                status TEXT NOT NULL
                    CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled')),
                base_model TEXT NOT NULL,
                epochs INTEGER NOT NULL,
                image_size INTEGER NOT NULL,
                device TEXT NOT NULL DEFAULT 'auto',
                progress REAL NOT NULL DEFAULT 0,
                metrics TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """,
            """
            CREATE TABLE models (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                training_job_id TEXT REFERENCES training_jobs(id) ON DELETE SET NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'development'
                    CHECK (status IN ('development', 'production', 'archived')),
                relative_path TEXT,
                metrics TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (project_id, name, version)
            )
            """,
            """
            CREATE TABLE cameras (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                source_type TEXT NOT NULL DEFAULT 'usb'
                    CHECK (source_type IN ('usb', 'rtsp')),
                device_index INTEGER,
                url TEXT,
                username TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE (project_id, name)
            )
            """,
            """
            CREATE TABLE events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                camera_id TEXT REFERENCES cameras(id) ON DELETE SET NULL,
                event_type TEXT NOT NULL,
                class_name TEXT,
                track_id INTEGER,
                confidence REAL,
                count INTEGER,
                snapshot_path TEXT,
                occurred_at TEXT NOT NULL
            )
            """,
            "CREATE INDEX idx_datasets_project ON datasets(project_id)",
            "CREATE INDEX idx_classes_project ON classes(project_id)",
            "CREATE INDEX idx_images_dataset ON images(dataset_id)",
            "CREATE INDEX idx_annotations_image ON annotations(image_id)",
            "CREATE INDEX idx_annotations_class ON annotations(class_id)",
            "CREATE INDEX idx_models_project ON models(project_id)",
            "CREATE INDEX idx_training_jobs_project ON training_jobs(project_id)",
            "CREATE INDEX idx_cameras_project ON cameras(project_id)",
            "CREATE INDEX idx_events_project_time ON events(project_id, occurred_at)",
        ),
    ),
    (2, (
        "ALTER TABLE images ADD COLUMN thumbnail_path TEXT",
        "CREATE UNIQUE INDEX idx_images_dataset_hash ON images(dataset_id, content_hash) WHERE content_hash IS NOT NULL",
    )),
    (3, (
        "CREATE TABLE pending_image_files (project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE, relative_path TEXT NOT NULL, PRIMARY KEY (project_id, relative_path))",
        "CREATE INDEX idx_images_created ON images(created_at, id)",
    )),
    (4, (
        "CREATE TABLE project_annotation_state (project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE, selected_class_id TEXT REFERENCES classes(id) ON DELETE SET NULL, next_class_index INTEGER NOT NULL CHECK (next_class_index >= 0))",
        "INSERT INTO project_annotation_state SELECT p.id, NULL, COALESCE(MAX(c.class_index) + 1, 0) FROM projects p LEFT JOIN classes c ON c.project_id = p.id GROUP BY p.id",
    )),
    (5, (
        "ALTER TABLE images ADD COLUMN annotation_revision INTEGER NOT NULL DEFAULT 0",
    )),
    (6, _migrate_training_jobs_phase_17),
]

SCHEMA_VERSION = MIGRATIONS[-1][0]


def database_path(root: Path) -> Path:
    return root / "data" / DATABASE_FILE


def connect(path: Path) -> sqlite3.Connection:
    """Open a connection with the settings every caller depends on."""
    connection = sqlite3.connect(path, timeout=10, isolation_level=None)
    connection.row_factory = sqlite3.Row
    try:
        # SQLite can return SQLITE_BUSY immediately while two first-open
        # connections switch journal mode. Retry that setup step within a bound.
        deadline = time.monotonic() + 10
        while True:
            try:
                connection.execute("PRAGMA journal_mode = WAL")
                break
            except sqlite3.OperationalError as error:
                if str(error) != "database is locked" or time.monotonic() >= deadline:
                    raise
                time.sleep(0.02)
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
    except BaseException:
        connection.close()
        raise
    return connection


@contextmanager
def session(path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def transaction(path: Path) -> Iterator[sqlite3.Connection]:
    """Run a unit of work that is committed together or rolled back entirely."""
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        try:
            yield connection
        except BaseException:
            connection.execute("ROLLBACK")
            raise
        connection.execute("COMMIT")
    finally:
        connection.close()


def initialize_database(root: Path) -> Path:
    """Create or upgrade the database, and return its path.

    Safe to call on every start: an up-to-date database is left untouched.
    """
    path = database_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Serialize the version read and migration together across desktop instances.
    with transaction(path) as connection:
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError(
                f"The workspace database uses schema version {version}, "
                f"but this version of Vision Studio supports {SCHEMA_VERSION}. "
                "Install a newer version of Vision Studio to open this workspace."
            )
        for target, statements in MIGRATIONS:
            if target <= version:
                continue
            if callable(statements):
                statements(connection)
            else:
                for statement in statements:
                    connection.execute(statement)
            connection.execute(f"PRAGMA user_version = {target}")
    return path
