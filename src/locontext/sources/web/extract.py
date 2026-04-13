from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from typing import override
from urllib.parse import urlparse

from .fetch import FetchedWebPage


@dataclass(slots=True)
class ExtractedBlock:
    kind: str
    text: str
    level: int | None = None


@dataclass(slots=True)
class ExtractedWebContent:
    title: str | None
    text: str
    structured_content: tuple[ExtractedBlock, ...] = ()
    linked_locators: tuple[str, ...] = ()
    page_signals: dict[str, int] | None = None


def extract_web_content(page: FetchedWebPage) -> ExtractedWebContent:
    content_type = page.content_type or ""
    if _looks_like_html(page.content, content_type):
        text, title, blocks, linked_locators, link_text = _extract_html(
            page.content, content_type
        )
    else:
        text = _decode_text(page.content, content_type)
        title = None
        blocks = (
            (ExtractedBlock(kind="paragraph", text=_normalize_whitespace(text)),)
            if text.strip()
            else ()
        )
        linked_locators = ()
        link_text = ""
    return ExtractedWebContent(
        title=title,
        text=_normalize_whitespace(text),
        structured_content=blocks,
        linked_locators=linked_locators,
        page_signals=_page_signals(text, blocks, page.resolved_locator, link_text),
    )


def _extract_html(
    content: bytes, content_type: str
) -> tuple[str, str | None, tuple[ExtractedBlock, ...], tuple[str, ...], str]:
    parser = _MinimalHTMLExtractor()
    parser.feed(_decode_text(content, content_type))
    parser.close()
    return (
        " ".join(parser.text_parts),
        parser.title_text,
        tuple(parser.blocks),
        tuple(parser.linked_locators),
        " ".join(parser.link_text_parts),
    )


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
        self.blocks: list[ExtractedBlock] = []
        self.linked_locators: list[str] = []
        self.link_text_parts: list[str] = []
        self._seen_links: set[str] = set()
        self._in_ignored_tag: bool = False
        self._in_title: bool = False
        self._in_link: bool = False
        self._block_tag: str | None = None
        self._block_level: int | None = None
        self._block_parts: list[str] = []

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
        elif tag in {"p", "li"}:
            self._start_block(tag, None)
        elif re.fullmatch(r"h[1-6]", tag):
            self._start_block("heading", int(tag[1]))
        elif tag == "a" and not self._in_ignored_tag:
            self._in_link = True
            href = dict(attrs).get("href")
            normalized = _normalize_link_target(href)
            if normalized is not None and normalized not in self._seen_links:
                self._seen_links.add(normalized)
                self.linked_locators.append(normalized)

    @override
    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self._in_ignored_tag = False
        elif tag == "title":
            self._in_title = False
        elif tag in {"p", "li"}:
            self._finish_block(tag)
        elif re.fullmatch(r"h[1-6]", tag):
            self._finish_block("heading")
        elif tag == "a":
            self._in_link = False

    @override
    def handle_data(self, data: str) -> None:
        if self._in_ignored_tag:
            return
        if self._in_title:
            self.title_parts.append(data)
            return
        if data.strip():
            self.text_parts.append(data)
            if self._in_link:
                self.link_text_parts.append(data)
            if self._block_tag is not None:
                self._block_parts.append(data)

    def _start_block(self, kind: str, level: int | None) -> None:
        if self._block_tag is not None:
            self._flush_block()
        self._block_tag = kind
        self._block_level = level
        self._block_parts = []

    def _finish_block(self, kind: str) -> None:
        if self._block_tag != kind:
            return
        self._flush_block()

    def _flush_block(self) -> None:
        if self._block_tag is None:
            return
        text = _normalize_whitespace(" ".join(self._block_parts))
        if text:
            self.blocks.append(
                ExtractedBlock(
                    kind=self._block_tag,
                    level=self._block_level,
                    text=text,
                )
            )
        self._block_tag = None
        self._block_level = None
        self._block_parts = []


def structured_content_as_dicts(
    blocks: tuple[ExtractedBlock, ...],
) -> list[dict[str, object]]:
    return [asdict(block) for block in blocks]


def _normalize_link_target(href: str | None) -> str | None:
    if href is None:
        return None

    normalized = href.strip()
    if not normalized or normalized.startswith("#"):
        return None

    parsed = urlparse(normalized)
    if parsed.scheme and parsed.scheme.lower() not in {"http", "https"}:
        return None

    return normalized


def _page_signals(
    text: str,
    blocks: tuple[ExtractedBlock, ...],
    resolved_locator: str,
    link_text: str = "",
) -> dict[str, int]:
    visible_text_chars = len(_normalize_whitespace(text))
    link_text_chars = len(_normalize_whitespace(link_text))
    paragraph_count = sum(1 for block in blocks if block.kind in {"paragraph", "p"})
    heading_count = sum(1 for block in blocks if block.kind == "heading")
    path_depth = len(
        [part for part in urlparse(resolved_locator).path.split("/") if part]
    )
    return {
        "visible_text_chars": visible_text_chars,
        "link_text_chars": link_text_chars,
        "paragraph_count": paragraph_count,
        "heading_count": heading_count,
        "path_depth": path_depth,
    }
