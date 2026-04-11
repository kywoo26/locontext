from __future__ import annotations

import unittest

import httpx

from locontext.sources.web.fetch import (
    WebHTTPStatusError,
    WebRequestError,
    fetch_web_page,
)


class WebFetchTest(unittest.TestCase):
    def test_fetches_with_injected_client_and_follows_redirects(self) -> None:
        requests: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(str(request.url))
            if request.url.path == "/start":
                return httpx.Response(
                    302, headers={"Location": "/final"}, request=request
                )
            return httpx.Response(
                200,
                headers={"Content-Type": "text/html; charset=utf-8"},
                text="<html><head><title>Doc</title></head><body>Hello</body></html>",
                request=request,
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            page = fetch_web_page("https://example.com/start", client=client)
        finally:
            client.close()

        self.assertEqual(
            requests, ["https://example.com/start", "https://example.com/final"]
        )
        self.assertEqual(page.requested_locator, "https://example.com/start")
        self.assertEqual(page.resolved_locator, "https://example.com/final")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.content_type, "text/html; charset=utf-8")

    def test_wraps_status_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(WebHTTPStatusError) as captured:
                _ = fetch_web_page("https://example.com/missing", client=client)
        finally:
            client.close()

        self.assertEqual(captured.exception.status_code, 404)
        self.assertEqual(captured.exception.locator, "https://example.com/missing")

    def test_wraps_request_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with self.assertRaises(WebRequestError) as captured:
                _ = fetch_web_page("https://example.com", client=client)
        finally:
            client.close()

        self.assertEqual(captured.exception.locator, "https://example.com")


if __name__ == "__main__":
    _ = unittest.main()
