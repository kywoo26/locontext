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


if __name__ == "__main__":
    _ = unittest.main()
