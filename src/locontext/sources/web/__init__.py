"""Web source helpers for locontext."""

from .canonicalize import CanonicalizedLocator, canonicalize_locator, infer_docset_root
from .discovery import filter_and_order_discovered_documents
from .extract import ExtractedWebContent, extract_web_content
from .fetch import (
    FetchedWebPage,
    WebFetchError,
    WebHTTPStatusError,
    WebRequestError,
    fetch_web_page,
)

__all__ = [
    "CanonicalizedLocator",
    "ExtractedWebContent",
    "FetchedWebPage",
    "canonicalize_locator",
    "extract_web_content",
    "filter_and_order_discovered_documents",
    "infer_docset_root",
    "fetch_web_page",
    "WebFetchError",
    "WebHTTPStatusError",
    "WebRequestError",
]
