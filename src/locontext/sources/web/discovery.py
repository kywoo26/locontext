from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlparse

from ...domain.models import DiscoveredDocument, Source
from .canonicalize import canonicalize_locator


def filter_and_order_discovered_documents(
    source: Source,
    candidates: Sequence[DiscoveredDocument],
) -> list[DiscoveredDocument]:
    base = urlparse(source.docset_root)
    base_path = base.path.rstrip("/")
    deduped: dict[str, DiscoveredDocument] = {}

    for candidate in candidates:
        normalized = canonicalize_locator(
            requested_locator=candidate.requested_locator,
            resolved_locator=candidate.resolved_locator,
        )
        parsed = urlparse(normalized.canonical_locator)
        path = parsed.path.rstrip("/")
        if parsed.netloc.lower() != base.netloc.lower():
            continue
        if base_path and not path.startswith(base_path):
            continue
        if normalized.canonical_locator not in deduped:
            deduped[normalized.canonical_locator] = DiscoveredDocument(
                requested_locator=normalized.requested_locator,
                resolved_locator=normalized.resolved_locator,
                canonical_locator=normalized.canonical_locator,
                title=candidate.title,
                content_hash=candidate.content_hash,
                metadata=dict(candidate.metadata),
            )

    return sorted(deduped.values(), key=_sort_key)


def _sort_key(document: DiscoveredDocument) -> tuple[int, str, str]:
    parsed = urlparse(document.canonical_locator)
    stripped_path = parsed.path.strip("/")
    depth = 0 if not stripped_path else len(stripped_path.split("/"))
    return depth, parsed.path.rstrip("/"), document.canonical_locator
