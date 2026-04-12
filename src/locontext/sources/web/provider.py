from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urljoin

import httpx

from ...domain.models import DiscoveredDocument, Source, SourceKind
from .canonicalize import canonicalize_locator
from .discovery import (
    filter_and_order_discovered_documents,
    filter_and_order_discovered_locators,
)
from .extract import ExtractedWebContent, extract_web_content
from .fetch import FetchedWebPage, fetch_web_page


@dataclass(slots=True)
class WebDiscoveryProvider:
    client: httpx.Client | None = None
    timeout: float | httpx.Timeout = 10.0
    max_pages: int = 20

    def discover(self, source: Source) -> list[DiscoveredDocument]:
        if source.source_kind is not SourceKind.WEB:
            return []

        if self.max_pages <= 0:
            return []

        discovered: list[DiscoveredDocument] = []
        pending: deque[str] = deque([source.requested_locator])
        seen_canonical: set[str] = set()
        queued_canonical: set[str] = {
            canonicalize_locator(source.requested_locator).canonical_locator
        }

        while pending and len(discovered) < self.max_pages:
            locator = pending.popleft()
            page = fetch_web_page(locator, client=self.client, timeout=self.timeout)
            extracted = extract_web_content(page)
            document = _to_discovered_document(page, extracted)
            in_scope = filter_and_order_discovered_documents(source, [document])
            if not in_scope:
                continue

            scoped_document = in_scope[0]
            if scoped_document.canonical_locator in seen_canonical:
                continue

            seen_canonical.add(scoped_document.canonical_locator)
            discovered.append(scoped_document)
            if len(discovered) >= self.max_pages:
                continue

            linked_locators = [
                urljoin(page.resolved_locator, linked_locator)
                for linked_locator in extracted.linked_locators
            ]
            for candidate in filter_and_order_discovered_locators(
                source, linked_locators
            ):
                if candidate in seen_canonical or candidate in queued_canonical:
                    continue
                queued_canonical.add(candidate)
                pending.append(candidate)

        return filter_and_order_discovered_documents(source, discovered)


def _to_discovered_document(
    page: FetchedWebPage,
    extracted: ExtractedWebContent,
) -> DiscoveredDocument:
    canonicalized = canonicalize_locator(
        requested_locator=page.requested_locator,
        resolved_locator=page.resolved_locator,
    )
    return DiscoveredDocument(
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


def _content_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()
