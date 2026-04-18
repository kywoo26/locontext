import httpx
import pytest

from locontext.sources.web.fetch import (
    WebHTTPStatusError,
    WebRequestError,
    fetch_web_page,
)


class TestWebFetch:
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
        assert requests == ["https://example.com/start", "https://example.com/final"]
        assert page.requested_locator == "https://example.com/start"
        assert page.resolved_locator == "https://example.com/final"
        assert page.status_code == 200
        assert page.content_type == "text/html; charset=utf-8"

    def test_wraps_status_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(WebHTTPStatusError) as captured:
                _ = fetch_web_page("https://example.com/missing", client=client)
        finally:
            client.close()
        assert captured.value.status_code == 404
        assert captured.value.locator == "https://example.com/missing"

    def test_wraps_request_errors(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            with pytest.raises(WebRequestError) as captured:
                _ = fetch_web_page("https://example.com", client=client)
        finally:
            client.close()
        assert captured.value.locator == "https://example.com"
