from __future__ import annotations

import sqlite3
import unittest

from locontext.app.sources import list_sources, register_source
from locontext.store.sqlite import SQLiteStore


class SourceRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.store = SQLiteStore(self.connection)
        self.store.ensure_schema()

    def test_register_source_creates_web_source(self) -> None:
        result = register_source(
            self.store,
            "https://docs.example.com/docs/getting-started?utm_source=test#intro",
        )

        self.assertTrue(result.created)
        self.assertEqual(
            result.source.canonical_locator,
            "https://docs.example.com/docs/getting-started",
        )
        self.assertEqual(result.source.docset_root, "https://docs.example.com")

    def test_register_source_dedupes_equivalent_urls(self) -> None:
        first = register_source(
            self.store,
            "https://docs.example.com/docs/getting-started?utm_source=test#intro",
        )
        second = register_source(
            self.store,
            "https://docs.example.com/docs/getting-started",
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.source.source_id, second.source.source_id)

    def test_list_sources_is_deterministic(self) -> None:
        register_source(self.store, "https://docs.example.com/docs/beta")
        register_source(self.store, "https://docs.example.com/docs/alpha")

        sources = list_sources(self.store)

        self.assertEqual(
            [source.canonical_locator for source in sources],
            [
                "https://docs.example.com/docs/alpha",
                "https://docs.example.com/docs/beta",
            ],
        )


if __name__ == "__main__":
    unittest.main()
