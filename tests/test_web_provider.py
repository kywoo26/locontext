from __future__ import annotations

import unittest

import httpx

from locontext.domain.models import Source, SourceKind
from locontext.sources.web.fetch import WebHTTPStatusError
from locontext.sources.web.provider import WebDiscoveryProvider


class WebProviderWarningContractTest(unittest.TestCase):
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
        self.addCleanup(client.close)
        provider = WebDiscoveryProvider(client=client)

        with self.assertRaises(WebHTTPStatusError):
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
        self.addCleanup(client.close)
        provider = WebDiscoveryProvider(client=client)

        outcome = provider.discover(self._source())

        self.assertEqual(len(outcome.documents), 2)
        self.assertEqual(outcome.warning_count, 1)
        self.assertEqual(len(outcome.warning_samples), 1)
        self.assertIn("/docs/bad", outcome.warning_samples[0].locator)


if __name__ == "__main__":
    _ = unittest.main()
