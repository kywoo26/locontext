from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import override

from .fetch import FetchedWebPage


@dataclass(slots=True)
class ExtractedWebContent:
    title: str | None
    text: str


def extract_web_content(page: FetchedWebPage) -> ExtractedWebContent:
    content_type = page.content_type or ""
    if _looks_like_html(page.content, content_type):
        text, title = _extract_html(page.content, content_type)
    else:
        text = _decode_text(page.content, content_type)
        title = None
    return ExtractedWebContent(title=title, text=_normalize_whitespace(text))


def _extract_html(content: bytes, content_type: str) -> tuple[str, str | None]:
    parser = _MinimalHTMLExtractor()
    parser.feed(_decode_text(content, content_type))
    parser.close()
    return " ".join(parser.text_parts), parser.title_text


def _decode_text(content: bytes, content_type: str) -> str:
    charset = _charset_from_content_type(content_type) or "utf-8"
    return content.decode(charset, errors="replace")


def _looks_like_html(content: bytes, content_type: str) -> bool:
    normalized = content_type.lower()
    if "html" in normalized:
        return True
    prefix = content.lstrip()[:20].lower()
    return prefix.startswith(b"<html") or prefix.startswith(b"<!doctype html")


def _charset_from_content_type(content_type: str) -> str | None:
    match = re.search(r"charset=([\w._-]+)", content_type, flags=re.IGNORECASE)
    if match is None:
        return None
    return match.group(1)


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


class _MinimalHTMLExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.text_parts: list[str] = []
        self.title_parts: list[str] = []
        self._in_ignored_tag: bool = False
        self._in_title: bool = False

    @property
    def title_text(self) -> str | None:
        title = _normalize_whitespace(" ".join(self.title_parts))
        return title or None

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._in_ignored_tag = True
        elif tag == "title":
            self._in_title = True

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._in_ignored_tag = False
        elif tag == "title":
            self._in_title = False

    @override
    def handle_data(self, data: str) -> None:
        if self._in_ignored_tag:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        if data.strip():
            self.text_parts.append(data)
