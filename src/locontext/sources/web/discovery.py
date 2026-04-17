from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import urlparse

from ...domain.models import DiscoveredDocument, Source
from .canonicalize import canonicalize_locator

_GITHUB_DOC_SURFACE_SEGMENTS = {"blob", "tree", "wiki"}
_GITHUB_MANAGEMENT_SEGMENTS = {"compare", "issues", "pulls", "releases"}
_GITHUB_CHROME_SEGMENTS = {
    "collections",
    "commits",
    "insights",
    "marketplace",
    "pulse",
    "search",
    "tags",
}


def filter_and_order_discovered_documents(
    source: Source,
    candidates: Sequence[DiscoveredDocument],
) -> list[DiscoveredDocument]:
    base = urlparse(source.docset_root)
    base_parts = _path_parts(base.path)
    github_repo_like = _is_github_repo_like(source, candidates)
    deduped: dict[str, DiscoveredDocument] = {}

    for candidate in candidates:
        normalized = canonicalize_locator(
            requested_locator=candidate.requested_locator,
            resolved_locator=candidate.resolved_locator,
        )
        parsed = urlparse(normalized.canonical_locator)
        candidate_parts = _path_parts(parsed.path)
        if parsed.netloc.lower() != base.netloc.lower():
            continue
        if not _is_in_scope(candidate_parts, base_parts):
            continue
        if github_repo_like and _is_suppressed_github_locator(
            candidate_parts, base_parts
        ):
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

    documents = list(deduped.values())
    if github_repo_like:
        return sorted(
            documents,
            key=lambda document: _github_sort_key(document, base_parts),
        )
    return sorted(documents, key=_sort_key)


def filter_and_order_discovered_locators(
    source: Source,
    candidates: Sequence[str],
) -> list[str]:
    ordered = filter_and_order_discovered_documents(
        source,
        [
            DiscoveredDocument(
                requested_locator=candidate,
                resolved_locator=candidate,
                canonical_locator=candidate,
            )
            for candidate in candidates
        ],
    )
    return [document.canonical_locator for document in ordered]


def _sort_key(document: DiscoveredDocument) -> tuple[int, str, str]:
    parsed = urlparse(document.canonical_locator)
    stripped_path = parsed.path.strip("/")
    depth = 0 if not stripped_path else len(stripped_path.split("/"))
    return depth, parsed.path.rstrip("/"), document.canonical_locator


def _path_parts(path: str) -> tuple[str, ...]:
    return tuple(part for part in path.split("/") if part)


def _is_in_scope(candidate_parts: tuple[str, ...], base_parts: tuple[str, ...]) -> bool:
    if not base_parts:
        return True
    if len(candidate_parts) < len(base_parts):
        return False
    return candidate_parts[: len(base_parts)] == base_parts


def _is_github_repo_like(
    source: Source,
    candidates: Sequence[DiscoveredDocument],
) -> bool:
    parsed = urlparse(source.docset_root)
    source_parts = _path_parts(parsed.path)
    if parsed.netloc.lower() == "github.com" and len(source_parts) >= 2:
        return True

    for candidate in candidates:
        child_segment = _child_segment_after_scope(
            source_parts, candidate.canonical_locator
        )
        if child_segment in _GITHUB_DOC_SURFACE_SEGMENTS:
            return True
    return False


def _child_segment_after_scope(
    source_parts: tuple[str, ...],
    locator: str,
) -> str | None:
    candidate_parts = _path_parts(urlparse(locator).path)
    if not _is_in_scope(candidate_parts, source_parts):
        return None
    if len(candidate_parts) <= len(source_parts):
        return None
    return candidate_parts[len(source_parts)].lower()


def _is_suppressed_github_locator(
    candidate_parts: tuple[str, ...],
    base_parts: tuple[str, ...],
) -> bool:
    if len(candidate_parts) <= len(base_parts):
        return False
    return candidate_parts[len(base_parts)].lower() in _GITHUB_CHROME_SEGMENTS


def _github_sort_key(
    document: DiscoveredDocument,
    base_parts: tuple[str, ...],
) -> tuple[int, str]:
    child_segment = _child_segment_after_scope(base_parts, document.canonical_locator)
    if child_segment is None:
        return (0, document.canonical_locator)
    if child_segment in _GITHUB_DOC_SURFACE_SEGMENTS:
        return (1, document.canonical_locator)
    if child_segment in _GITHUB_MANAGEMENT_SEGMENTS:
        return (2, document.canonical_locator)
    return (3, document.canonical_locator)
