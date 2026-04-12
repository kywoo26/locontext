from __future__ import annotations

import unittest

from locontext.domain.models import DiscoveredDocument, Source, SourceKind
from locontext.sources.web.discovery import filter_and_order_discovered_documents


class WebDiscoveryPolicyTest(unittest.TestCase):
    def _source(self) -> Source:
        return Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )

    def test_filters_same_host_only(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source(),
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/intro",
                    resolved_locator="https://docs.example.com/docs/intro",
                    canonical_locator="https://docs.example.com/docs/intro",
                ),
                DiscoveredDocument(
                    requested_locator="https://other.example.com/docs/intro",
                    resolved_locator="https://other.example.com/docs/intro",
                    canonical_locator="https://other.example.com/docs/intro",
                ),
            ],
        )

        self.assertEqual(
            [item.canonical_locator for item in ordered],
            ["https://docs.example.com/docs/intro"],
        )

    def test_filters_docset_root_only(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source(),
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/blog/post",
                    resolved_locator="https://docs.example.com/blog/post",
                    canonical_locator="https://docs.example.com/blog/post",
                ),
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                ),
            ],
        )

        self.assertEqual(
            [item.canonical_locator for item in ordered],
            ["https://docs.example.com/docs/guide"],
        )

    def test_dedupes_canonical_locators(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source(),
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/intro#fragment",
                    resolved_locator="https://docs.example.com/docs/intro",
                    canonical_locator="https://docs.example.com/docs/intro",
                ),
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/intro?utm_source=test",
                    resolved_locator="https://docs.example.com/docs/intro",
                    canonical_locator="https://docs.example.com/docs/intro",
                ),
            ],
        )

        self.assertEqual(
            [item.canonical_locator for item in ordered],
            ["https://docs.example.com/docs/intro"],
        )

    def test_orders_shallower_paths_first_then_lexically(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source(),
            [
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
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs",
                    resolved_locator="https://docs.example.com/docs",
                    canonical_locator="https://docs.example.com/docs",
                ),
            ],
        )

        self.assertEqual(
            [item.canonical_locator for item in ordered],
            [
                "https://docs.example.com/docs",
                "https://docs.example.com/docs/alpha",
                "https://docs.example.com/docs/beta",
                "https://docs.example.com/docs/beta/deep",
            ],
        )


if __name__ == "__main__":
    _ = unittest.main()
