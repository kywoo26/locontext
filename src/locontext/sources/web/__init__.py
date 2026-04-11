"""Web source helpers for locontext."""

from .canonicalize import CanonicalizedLocator, canonicalize_locator, infer_docset_root
from .discovery import filter_and_order_discovered_documents

__all__ = [
    "CanonicalizedLocator",
    "canonicalize_locator",
    "filter_and_order_discovered_documents",
    "infer_docset_root",
]
