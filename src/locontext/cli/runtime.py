from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..config.settings import Settings, load_settings
from ..store.migration_runner import apply_migrations
from ..store.sqlite import SQLiteStore


@dataclass(slots=True)
class Runtime:
    project_root: Path
    settings: Settings
    db_path: Path
    connection: sqlite3.Connection
    store: SQLiteStore

    def close(self) -> None:
        self.connection.close()


@dataclass(slots=True)
class InitResult:
    created_config: bool
    created_data_dir: bool
    created_database: bool
    config_path: Path
    data_dir: Path
    db_path: Path


def open_runtime(project_root: Path | None = None) -> Runtime:
    resolved_root = project_root or Path.cwd()
    settings = load_settings(resolved_root)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = settings.data_dir / "locontext.db"
    connection = sqlite3.connect(db_path)
    store = SQLiteStore(connection)
    apply_migrations(connection)
    return Runtime(
        project_root=resolved_root,
        settings=settings,
        db_path=db_path,
        connection=connection,
        store=store,
    )


def project_paths(project_root: Path | None = None) -> tuple[Path, Path, Path]:
    resolved_root = project_root or Path.cwd()
    config_path = resolved_root / "locontext.toml"
    data_dir = load_settings(resolved_root).data_dir
    db_path = data_dir / "locontext.db"
    return resolved_root, config_path, db_path


def is_initialized(project_root: Path | None = None) -> bool:
    _root, config_path, db_path = project_paths(project_root)
    return config_path.exists() and db_path.exists()


def initialize_project(project_root: Path | None = None) -> InitResult:
    resolved_root = project_root or Path.cwd()
    config_path = resolved_root / "locontext.toml"
    created_config = False
    if not config_path.exists():
        config_path.write_text('data_dir = ".locontext"\n', encoding="utf-8")
        created_config = True

    settings = load_settings(resolved_root)
    created_data_dir = not settings.data_dir.exists()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    db_path = settings.data_dir / "locontext.db"
    created_database = not db_path.exists()
    connection = sqlite3.connect(db_path)
    try:
        _ = apply_migrations(connection)
    finally:
        connection.close()

    return InitResult(
        created_config=created_config,
        created_data_dir=created_data_dir,
        created_database=created_database,
        config_path=config_path,
        data_dir=settings.data_dir,
        db_path=db_path,
    )
