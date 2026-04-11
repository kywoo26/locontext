from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_DEFAULT_PORTS = {"http": 80, "https": 443}
_STRIP_PARAMS = {"fbclid", "gclid"}
_ROOT_HINT_SEGMENTS = {"docs", "doc", "documentation", "api", "reference", "sdk", "cli"}


@dataclass(slots=True)
class CanonicalizedLocator:
    requested_locator: str
    resolved_locator: str
    canonical_locator: str


def canonicalize_locator(
    requested_locator: str,
    resolved_locator: str | None = None,
) -> CanonicalizedLocator:
    normalized_requested = _normalize_url(requested_locator)
    normalized_resolved = (
        _normalize_url(resolved_locator) if resolved_locator else normalized_requested
    )
    return CanonicalizedLocator(
        requested_locator=normalized_requested,
        resolved_locator=normalized_resolved,
        canonical_locator=normalized_resolved,
    )


def infer_docset_root(locator: str) -> str:
    parsed = urlparse(_normalize_url(locator))
    host_root = urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))
    path = parsed.path or ""

    if path.endswith("/llms-full.txt"):
        return host_root + path.removesuffix("/llms-full.txt")
    if path.endswith("/llms.txt"):
        return host_root + path.removesuffix("/llms.txt")

    host = parsed.netloc.lower()
    if host.startswith(("docs.", "doc.", "api.")):
        return host_root

    parts = [part for part in path.split("/") if part]
    if parts and parts[0].lower() in _ROOT_HINT_SEGMENTS:
        return f"{host_root}/{parts[0]}"

    return host_root


def _normalize_url(locator: str) -> str:
    parsed = urlparse(locator)
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    if host and port and _DEFAULT_PORTS.get(scheme) != port:
        netloc = f"{host}:{port}"
    else:
        netloc = host

    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    filtered_query_items: list[tuple[str, str]] = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().startswith("utm_"):
            continue
        if key.lower() in _STRIP_PARAMS:
            continue
        filtered_query_items.append((key, value))
    filtered_query_items.sort()
    query = urlencode(filtered_query_items, doseq=True)

    return urlunparse((scheme, netloc, path, "", query, ""))
