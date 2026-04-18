import httpx
import pytest

from locontext.domain.models import Source, SourceKind
from locontext.sources.web.fetch import WebHTTPStatusError
from locontext.sources.web.provider import WebDiscoveryProvider


class TestWebProviderWarningContract:
    def _source(self) -> Source:
        return Source(
            source_id="source-1",
            source_kind=SourceKind.WEB,
            requested_locator="https://docs.example.com/docs",
            resolved_locator="https://docs.example.com/docs",
            canonical_locator="https://docs.example.com/docs",
            docset_root="https://docs.example.com/docs",
        )

    def test_seed_fetch_failure_remains_fatal(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = WebDiscoveryProvider(client=client)
        with pytest.raises(WebHTTPStatusError):
            _ = provider.discover(self._source())

    def test_child_fetch_failure_becomes_warning_not_total_failure(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/docs":
                return httpx.Response(
                    200,
                    request=request,
                    text='<html><body><a href="/docs/good">Good</a><a href="/docs/bad">Bad</a></body></html>',
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            if request.url.path == "/docs/good":
                return httpx.Response(
                    200,
                    request=request,
                    text="<html><body><p>Good page</p></body></html>",
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            return httpx.Response(404, request=request)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = WebDiscoveryProvider(client=client)
        outcome = provider.discover(self._source())
        assert len(outcome.documents) == 2
        assert outcome.warning_count == 1
        assert len(outcome.warning_samples) == 1
        assert "/docs/bad" in outcome.warning_samples[0].locator
