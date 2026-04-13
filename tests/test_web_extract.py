from __future__ import annotations

import unittest

from locontext.sources.web.extract import extract_web_content
from locontext.sources.web.fetch import FetchedWebPage


class WebExtractTest(unittest.TestCase):
    def test_extracts_title_and_visible_text_from_html(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/guide",
            resolved_locator="https://example.com/guide",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=(
                b"<html><head><title> Guide </title><style>body{}</style></head>"
                b"<body><h1>Hello</h1><script>ignored()</script><p>world</p></body></html>"
            ),
        )

        extracted = extract_web_content(page)

        self.assertEqual(extracted.title, "Guide")
        self.assertEqual(extracted.text, "Hello world")
        self.assertEqual(extracted.linked_locators, ())

    def test_extracts_http_links_in_document_order(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/guide",
            resolved_locator="https://example.com/guide",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=(
                b"<html><body>"
                b'<a href="/docs/start">Start</a>'
                b'<a href="#section">Section</a>'
                b'<a href="https://example.com/docs/next">Next</a>'
                b'<a href="mailto:test@example.com">Email</a>'
                b'<a href="/docs/start">Duplicate</a>'
                b"</body></html>"
            ),
        )

        extracted = extract_web_content(page)

        self.assertEqual(
            extracted.linked_locators,
            ("/docs/start", "https://example.com/docs/next"),
        )

    def test_extracts_plain_text_without_title(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/readme.txt",
            resolved_locator="https://example.com/readme.txt",
            status_code=200,
            headers={"content-type": "text/plain; charset=utf-8"},
            content=b"Line 1\n\nLine 2  ",
        )

        extracted = extract_web_content(page)

        self.assertIsNone(extracted.title)
        self.assertEqual(extracted.text, "Line 1 Line 2")
        self.assertEqual(extracted.linked_locators, ())

    def test_extracts_page_signals_for_policy_use(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/guide",
            resolved_locator="https://example.com/guide",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=(
                b"<html><body>"
                b"<h1>Guide</h1>"
                b"<p>Hello world paragraph.</p>"
                b"<p>Another paragraph.</p>"
                b'<a href="/nav">Navigation</a>'
                b"</body></html>"
            ),
        )

        extracted = extract_web_content(page)

        if extracted.page_signals is None:
            self.fail("expected page signals")
        self.assertGreater(extracted.page_signals["visible_text_chars"], 10)
        self.assertEqual(extracted.page_signals["paragraph_count"], 2)
        self.assertEqual(extracted.page_signals["heading_count"], 1)
        self.assertGreater(extracted.page_signals["link_text_chars"], 0)


if __name__ == "__main__":
    _ = unittest.main()
