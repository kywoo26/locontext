from __future__ import annotations

import unittest

from locontext.sources.web.canonicalize import canonicalize_locator, infer_docset_root


class CanonicalizeLocatorTest(unittest.TestCase):
    def test_removes_default_port_and_fragment(self) -> None:
        result = canonicalize_locator("HTTPS://Docs.Example.com:443/guide/start/#intro")
        self.assertEqual(
            result.canonical_locator, "https://docs.example.com/guide/start"
        )

    def test_strips_tracking_params_but_keeps_semantic_params(self) -> None:
        result = canonicalize_locator(
            "https://docs.example.com/search?utm_source=x&page=2&fbclid=y"
        )
        self.assertEqual(
            result.canonical_locator, "https://docs.example.com/search?page=2"
        )

    def test_uses_resolved_locator_as_canonical_base(self) -> None:
        result = canonicalize_locator(
            requested_locator="https://docs.example.com/start",
            resolved_locator="https://docs.example.com/guide/intro/?utm_campaign=test",
        )
        self.assertEqual(result.requested_locator, "https://docs.example.com/start")
        self.assertEqual(
            result.resolved_locator, "https://docs.example.com/guide/intro"
        )
        self.assertEqual(
            result.canonical_locator, "https://docs.example.com/guide/intro"
        )

    def test_infers_docset_root_for_docs_sites(self) -> None:
        self.assertEqual(
            infer_docset_root("https://example.com/docs/getting-started"),
            "https://example.com/docs",
        )

    def test_infers_repo_scoped_roots_for_github_urls(self) -> None:
        self.assertEqual(
            infer_docset_root("https://github.com/org/repo"),
            "https://github.com/org/repo",
        )
        self.assertEqual(
            infer_docset_root("https://github.com/org/repo/blob/main/README.md"),
            "https://github.com/org/repo",
        )
        self.assertEqual(
            infer_docset_root("https://github.com/org/repo/tree/main/docs"),
            "https://github.com/org/repo",
        )

    def test_keeps_article_and_blog_leaf_urls_exact(self) -> None:
        self.assertEqual(
            infer_docset_root("https://example.com/blog/post-slug"),
            "https://example.com/blog/post-slug",
        )
        self.assertEqual(
            infer_docset_root("https://example.com/news/2026/important-update"),
            "https://example.com/news/2026/important-update",
        )

    def test_preserves_docs_site_and_llms_parent_path_rules(self) -> None:
        self.assertEqual(
            infer_docset_root("https://docs.example.com/guide/start"),
            "https://docs.example.com",
        )
        self.assertEqual(
            infer_docset_root("https://example.com/docs/start"),
            "https://example.com/docs",
        )
        self.assertEqual(
            infer_docset_root("https://example.com/docs/llms.txt"),
            "https://example.com/docs",
        )
        self.assertEqual(
            infer_docset_root("https://example.com/docs/llms-full.txt"),
            "https://example.com/docs",
        )

    def test_does_not_repo_scope_non_repo_github_host_pages(self) -> None:
        self.assertEqual(
            infer_docset_root("https://github.com/marketplace"),
            "https://github.com",
        )


if __name__ == "__main__":
    unittest.main()
