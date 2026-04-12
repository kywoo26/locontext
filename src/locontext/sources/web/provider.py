from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import httpx

from ...domain.models import DiscoveredDocument, Source, SourceKind
from .canonicalize import canonicalize_locator
from .extract import extract_web_content
from .fetch import fetch_web_page


@dataclass(slots=True)
class WebDiscoveryProvider:
    client: httpx.Client | None = None
    timeout: float | httpx.Timeout = 10.0

    def discover(self, source: Source) -> list[DiscoveredDocument]:
        if source.source_kind is not SourceKind.WEB:
            return []

        page = fetch_web_page(
            source.requested_locator,
            client=self.client,
            timeout=self.timeout,
        )
        extracted = extract_web_content(page)
        canonicalized = canonicalize_locator(
            requested_locator=page.requested_locator,
            resolved_locator=page.resolved_locator,
        )
        return [
            DiscoveredDocument(
                requested_locator=canonicalized.requested_locator,
                resolved_locator=canonicalized.resolved_locator,
                canonical_locator=canonicalized.canonical_locator,
                title=extracted.title,
                content_hash=_content_hash(extracted.text),
                metadata={
                    "status_code": page.status_code,
                    "content_type": page.content_type,
                    "extracted_text": extracted.text,
                },
            )
        ]


def _content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()
