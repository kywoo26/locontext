from __future__ import annotations

import sqlite3
import unittest
from importlib import import_module
from typing import Protocol, cast


class _ApplyMigrations(Protocol):
    def __call__(self, connection: sqlite3.Connection) -> None: ...


class StoreMigrationsTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        super().setUp()
        self.connection = sqlite3.connect(":memory:")

    def tearDown(self) -> None:  # pyright: ignore[reportImplicitOverride]
        self.connection.close()
        super().tearDown()

    def _apply_migrations(self) -> None:
        module = import_module("locontext.store.migrations")
        apply_migrations = cast(
            _ApplyMigrations | None,
            getattr(module, "apply_migrations", None),
        )
        if apply_migrations is None:
            self.fail("expected locontext.store.migrations.apply_migrations")
        apply_migrations(self.connection)

    def test_apply_migrations_bootstraps_schema_and_records_version(self) -> None:
        self._apply_migrations()

        table_rows = cast(
            list[tuple[str]],
            self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall(),
        )
        table_names = {row[0] for row in table_rows}
        self.assertTrue(
            {
                "schema_migrations",
                "sources",
                "snapshots",
                "documents",
                "chunks",
                "chunk_fts",
                "chunk_fts_data",
                "chunk_fts_idx",
                "chunk_fts_docsize",
                "chunk_fts_config",
            }.issubset(table_names)
        )
        applied_versions = self.connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        self.assertEqual(applied_versions, [("0001_initial.sql",)])

    def test_apply_migrations_is_a_no_op_when_all_versions_are_already_applied(
        self,
    ) -> None:
        self._apply_migrations()
        before_versions = self.connection.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        before_table_names = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name ASC"
        ).fetchall()

        self._apply_migrations()

        after_versions = self.connection.execute(
            "SELECT version, applied_at FROM schema_migrations ORDER BY version ASC"
        ).fetchall()
        after_table_names = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name ASC"
        ).fetchall()
        self.assertEqual(after_versions, before_versions)
        self.assertEqual(after_table_names, before_table_names)


if __name__ == "__main__":
    _ = unittest.main()
