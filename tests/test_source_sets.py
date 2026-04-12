from __future__ import annotations

import sqlite3
import unittest

from locontext.app.sources import create_source_set, get_source_set, list_source_sets
from locontext.domain.models import Source, SourceKind
from locontext.store.sqlite import SQLiteStore


class SourceSetAppTest(unittest.TestCase):
    connection: sqlite3.Connection  # pyright: ignore[reportUninitializedInstanceVariable]
    store: SQLiteStore  # pyright: ignore[reportUninitializedInstanceVariable]

    def setUp(self) -> None:  # pyright: ignore[reportImplicitOverride]
        super().setUp()
        self.connection = sqlite3.connect(":memory:")
        self.store = SQLiteStore(self.connection)
        self.store.ensure_schema()

    def tearDown(self) -> None:  # pyright: ignore[reportImplicitOverride]
        self.connection.close()
        super().tearDown()

    def _seed_source(self, source_id: str, canonical_locator: str) -> None:
        self.store.upsert_source(
            Source(
                source_id=source_id,
                source_kind=SourceKind.WEB,
                requested_locator=canonical_locator,
                resolved_locator=canonical_locator,
                canonical_locator=canonical_locator,
                docset_root="https://docs.example.com",
            )
        )

    def test_create_source_set_collapses_duplicate_source_ids(self) -> None:
        self._seed_source("source-alpha", "https://docs.example.com/alpha")
        self._seed_source("source-beta", "https://docs.example.com/beta")

        result = create_source_set(
            self.store,
            "docs",
            ["source-beta", "source-alpha", "source-beta", "source-beta"],
        )

        self.assertTrue(result.created)
        self.assertEqual(result.duplicate_source_ids, ("source-beta", "source-beta"))
        self.assertEqual(
            [
                (member.source_id, member.canonical_locator, member.member_index)
                for member in result.source_set.members
            ],
            [
                ("source-beta", "https://docs.example.com/beta", 0),
                ("source-alpha", "https://docs.example.com/alpha", 1),
            ],
        )

        loaded = get_source_set(self.store, "docs")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded, result.source_set)

    def test_create_source_set_reuses_existing_named_set(self) -> None:
        self._seed_source("source-alpha", "https://docs.example.com/alpha")
        self._seed_source("source-beta", "https://docs.example.com/beta")

        first = create_source_set(self.store, "docs", ["source-alpha"])
        second = create_source_set(self.store, "docs", ["source-beta", "source-alpha"])

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(
            first.source_set.source_set_id, second.source_set.source_set_id
        )
        self.assertEqual(
            [member.source_id for member in second.source_set.members],
            ["source-beta", "source-alpha"],
        )

    def test_create_source_set_requires_all_sources_to_exist(self) -> None:
        self._seed_source("source-present", "https://docs.example.com/present")

        with self.assertRaisesRegex(KeyError, r"source-missing"):
            _ = create_source_set(
                self.store,
                "docs",
                ["source-present", "source-missing"],
            )

        self.assertEqual(list_source_sets(self.store), [])
        self.assertIsNone(self.store.get_source_set("docs"))

    def test_list_source_sets_is_sorted_by_name(self) -> None:
        self._seed_source("source-alpha", "https://docs.example.com/alpha")
        self._seed_source("source-beta", "https://docs.example.com/beta")

        _ = create_source_set(self.store, "zeta", ["source-beta"])
        _ = create_source_set(self.store, "alpha", ["source-alpha"])

        rows = list_source_sets(self.store)

        self.assertEqual(
            [source_set.set_name for source_set in rows], ["alpha", "zeta"]
        )
        self.assertEqual(
            [
                [member.source_id for member in source_set.members]
                for source_set in rows
            ],
            [["source-alpha"], ["source-beta"]],
        )


if __name__ == "__main__":
    _ = unittest.main()
