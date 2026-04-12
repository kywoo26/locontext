from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from importlib.resources import files
from typing import Final, cast

MIGRATIONS_PACKAGE: Final = "locontext.store.migrations"
MIGRATION_STATE_TABLE: Final = "schema_migrations"


@dataclass(frozen=True, slots=True)
class Migration:
    version: str
    sql: str


def apply_migrations(connection: sqlite3.Connection) -> None:
    _ = connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_STATE_TABLE} (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied_version_rows = cast(
        list[tuple[str]],
        connection.execute(
            f"SELECT version FROM {MIGRATION_STATE_TABLE} ORDER BY version ASC"
        ).fetchall(),
    )
    applied_versions = {row[0] for row in applied_version_rows}
    pending_migrations = [
        migration
        for migration in load_migrations()
        if migration.version not in applied_versions
    ]
    for migration in pending_migrations:
        _ = connection.executescript(migration.sql)
        _ = connection.execute(
            f"INSERT INTO {MIGRATION_STATE_TABLE} (version) VALUES (?)",
            (migration.version,),
        )
    connection.commit()


def load_migrations() -> list[Migration]:
    migration_root = files(MIGRATIONS_PACKAGE)
    migrations = [
        Migration(version=resource.name, sql=resource.read_text(encoding="utf-8"))
        for resource in migration_root.iterdir()
        if resource.is_file() and resource.name.endswith(".sql")
    ]
    return sorted(migrations, key=lambda migration: migration.version)
