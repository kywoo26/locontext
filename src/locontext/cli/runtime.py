from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from ..config.settings import Settings, load_settings
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


def open_runtime(project_root: Path | None = None) -> Runtime:
    resolved_root = project_root or Path.cwd()
    settings = load_settings(resolved_root)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db_path = settings.data_dir / "locontext.db"
    connection = sqlite3.connect(db_path)
    store = SQLiteStore(connection)
    store.ensure_schema()
    return Runtime(
        project_root=resolved_root,
        settings=settings,
        db_path=db_path,
        connection=connection,
        store=store,
    )
