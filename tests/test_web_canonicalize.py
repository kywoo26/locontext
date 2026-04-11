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

    def test_infers_docset_root(self) -> None:
        self.assertEqual(
            infer_docset_root("https://example.com/docs/getting-started"),
            "https://example.com/docs",
        )


if __name__ == "__main__":
    unittest.main()
