from locontext.sources.web.extract import extract_web_content
from locontext.sources.web.fetch import FetchedWebPage


class TestWebExtract:
    def test_extracts_title_and_visible_text_from_html(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/guide",
            resolved_locator="https://example.com/guide",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b"<html><head><title> Guide </title><style>body{}</style></head><body><h1>Hello</h1><script>ignored()</script><p>world</p></body></html>",
        )
        extracted = extract_web_content(page)
        assert extracted.title == "Guide"
        assert extracted.text == "Hello world"
        assert extracted.linked_locators == ()

    def test_extracts_http_links_in_document_order(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/guide",
            resolved_locator="https://example.com/guide",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b'<html><body><a href="/docs/start">Start</a><a href="#section">Section</a><a href="https://example.com/docs/next">Next</a><a href="mailto:test@example.com">Email</a><a href="/docs/start">Duplicate</a></body></html>',
        )
        extracted = extract_web_content(page)
        assert extracted.linked_locators == (
            "/docs/start",
            "https://example.com/docs/next",
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
        assert extracted.title is None
        assert extracted.text == "Line 1 Line 2"
        assert extracted.linked_locators == ()

    def test_extracts_page_signals_for_policy_use(self) -> None:
        page = FetchedWebPage(
            requested_locator="https://example.com/guide",
            resolved_locator="https://example.com/guide",
            status_code=200,
            headers={"content-type": "text/html; charset=utf-8"},
            content=b'<html><body><h1>Guide</h1><p>Hello world paragraph.</p><p>Another paragraph.</p><a href="/nav">Navigation</a></body></html>',
        )
        extracted = extract_web_content(page)
        if extracted.page_signals is None:
            raise AssertionError("expected page signals")
        assert extracted.page_signals["visible_text_chars"] > 10
        assert extracted.page_signals["paragraph_count"] == 2
        assert extracted.page_signals["heading_count"] == 1
        assert extracted.page_signals["link_text_chars"] > 0
