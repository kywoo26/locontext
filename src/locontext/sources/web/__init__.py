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
from .policy import BoundaryDecision, WebPageSignals, decide_page_admission

__all__ = [
    "CanonicalizedLocator",
    "BoundaryDecision",
    "ExtractedWebContent",
    "FetchedWebPage",
    "WebPageSignals",
    "canonicalize_locator",
    "decide_page_admission",
    "extract_web_content",
    "filter_and_order_discovered_documents",
    "infer_docset_root",
    "fetch_web_page",
    "WebFetchError",
    "WebHTTPStatusError",
    "WebRequestError",
]
