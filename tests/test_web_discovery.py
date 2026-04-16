from __future__ import annotations

import unittest

from locontext.domain.models import DiscoveredDocument, Source, SourceKind
from locontext.sources.web.discovery import filter_and_order_discovered_documents


class WebDiscoveryPolicyTest(unittest.TestCase):
    def _source(self, docset_root: str = "https://docs.example.com/docs") -> Source:
        return Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root=docset_root,
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

    def test_filters_repo_root_scope_before_off_scope_chrome_pages(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source("https://github.com/code-yeongyu/oh-my-openagent"),
            [
                DiscoveredDocument(
                    requested_locator="https://github.com/code-yeongyu/oh-my-openagent",
                    resolved_locator="https://github.com/code-yeongyu/oh-my-openagent",
                    canonical_locator="https://github.com/code-yeongyu/oh-my-openagent",
                ),
                DiscoveredDocument(
                    requested_locator="https://github.com/collections",
                    resolved_locator="https://github.com/collections",
                    canonical_locator="https://github.com/collections",
                ),
                DiscoveredDocument(
                    requested_locator="https://github.com/pricing",
                    resolved_locator="https://github.com/pricing",
                    canonical_locator="https://github.com/pricing",
                ),
            ],
        )

        self.assertEqual(
            [item.canonical_locator for item in ordered],
            ["https://github.com/code-yeongyu/oh-my-openagent"],
        )

    def test_filters_article_leaf_scope_before_unrelated_host_pages(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source("https://news.example.com/blog/post"),
            [
                DiscoveredDocument(
                    requested_locator="https://news.example.com/blog/post",
                    resolved_locator="https://news.example.com/blog/post",
                    canonical_locator="https://news.example.com/blog/post",
                ),
                DiscoveredDocument(
                    requested_locator="https://news.example.com/blog/post/comments",
                    resolved_locator="https://news.example.com/blog/post/comments",
                    canonical_locator="https://news.example.com/blog/post/comments",
                ),
                DiscoveredDocument(
                    requested_locator="https://news.example.com/blog/archive",
                    resolved_locator="https://news.example.com/blog/archive",
                    canonical_locator="https://news.example.com/blog/archive",
                ),
                DiscoveredDocument(
                    requested_locator="https://news.example.com/docs/guide",
                    resolved_locator="https://news.example.com/docs/guide",
                    canonical_locator="https://news.example.com/docs/guide",
                ),
            ],
        )

        self.assertEqual(
            [item.canonical_locator for item in ordered],
            [
                "https://news.example.com/blog/post",
                "https://news.example.com/blog/post/comments",
            ],
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

    def test_keeps_metadata_for_second_stage_boundary_policy(self) -> None:
        ordered = filter_and_order_discovered_documents(
            self._source(),
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/intro",
                    resolved_locator="https://docs.example.com/docs/intro",
                    canonical_locator="https://docs.example.com/docs/intro",
                    metadata={"page_signals": {"visible_text_chars": 100}},
                )
            ],
        )

        self.assertEqual(
            ordered[0].metadata["page_signals"], {"visible_text_chars": 100}
        )


if __name__ == "__main__":
    _ = unittest.main()
