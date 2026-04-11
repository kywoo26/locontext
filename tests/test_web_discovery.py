from __future__ import annotations

import unittest

from locontext.domain.models import DiscoveredDocument, Source, SourceKind
from locontext.sources.web.discovery import filter_and_order_discovered_documents


class DiscoveryOrderingTest(unittest.TestCase):
    def test_filters_off_root_and_off_host_and_dedupes(self) -> None:
        source = Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )
        documents = [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/intro",
                resolved_locator="https://docs.example.com/docs/intro",
                canonical_locator="https://docs.example.com/docs/intro",
            ),
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/intro#fragment",
                resolved_locator="https://docs.example.com/docs/intro",
                canonical_locator="https://docs.example.com/docs/intro",
            ),
            DiscoveredDocument(
                requested_locator="https://docs.example.com/blog/post",
                resolved_locator="https://docs.example.com/blog/post",
                canonical_locator="https://docs.example.com/blog/post",
            ),
            DiscoveredDocument(
                requested_locator="https://other.example.com/docs/intro",
                resolved_locator="https://other.example.com/docs/intro",
                canonical_locator="https://other.example.com/docs/intro",
            ),
        ]

        ordered = filter_and_order_discovered_documents(source, documents)
        self.assertEqual(
            [item.canonical_locator for item in ordered],
            ["https://docs.example.com/docs/intro"],
        )

    def test_orders_shallower_paths_first_then_lexically(self) -> None:
        source = Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )
        documents = [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/beta/deep",
                resolved_locator="https://docs.example.com/docs/beta/deep",
                canonical_locator="https://docs.example.com/docs/beta/deep",
            ),
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/alpha",
                resolved_locator="https://docs.example.com/docs/alpha",
                canonical_locator="https://docs.example.com/docs/alpha",
            ),
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/beta",
                resolved_locator="https://docs.example.com/docs/beta",
                canonical_locator="https://docs.example.com/docs/beta",
            ),
        ]

        ordered = filter_and_order_discovered_documents(source, documents)
        self.assertEqual(
            [item.canonical_locator for item in ordered],
            [
                "https://docs.example.com/docs/alpha",
                "https://docs.example.com/docs/beta",
                "https://docs.example.com/docs/beta/deep",
            ],
        )


if __name__ == "__main__":
    unittest.main()
