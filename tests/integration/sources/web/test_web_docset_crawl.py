import sqlite3
import tempfile
import threading
from collections.abc import Sequence
from contextlib import ExitStack, contextmanager
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import override

import httpx
import pytest

from locontext.app.refresh import RefreshOrchestrator
from locontext.domain.models import (
    DiscoveredDocument,
    Document,
    Snapshot,
    Source,
    SourceKind,
)
from locontext.sources.web.discovery import filter_and_order_discovered_documents
from locontext.sources.web.provider import WebDiscoveryProvider
from locontext.store.sqlite import SQLiteStore

pytestmark = pytest.mark.integration


class _RecordingIndexingEngine:
    def __init__(self) -> None:
        super().__init__()
        self.reindex_calls: list[tuple[str, str, int]] = []

    def reindex_snapshot(
        self, source: Source, snapshot: Snapshot, documents: Sequence[Document]
    ) -> None:
        self.reindex_calls.append(
            (source.source_id, snapshot.snapshot_id, len(documents))
        )

    def remove_source(self, source_id: str) -> None:
        _ = source_id


@contextmanager
def _serve_fixture(routes: dict[str, bytes]):
    requests: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            requests.append(self.path)
            body = routes.get(self.path)
            if body is None:
                _ = self.send_response(404)
                self.end_headers()
                return

            _ = self.send_response(200)
            self.send_header("content-type", "text/html; charset=utf-8")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            _ = self.wfile.write(body)

        @override
        def log_message(self, format: str, *args: object) -> None:
            _ = format, args

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = "127.0.0.1"
        port = server.server_port
        yield f"http://{host}:{port}", requests
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _source() -> Source:
    return Source(
        source_id="source-1",
        source_kind=SourceKind.WEB,
        requested_locator="https://docs.example.com/docs",
        resolved_locator="https://docs.example.com/docs",
        canonical_locator="https://docs.example.com/docs",
        docset_root="https://docs.example.com/docs",
    )


class TestWebDocsetCrawlPolicy:
    def test_refresh_ingests_only_in_scope_local_pages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            docs_root = root / "docs"
            docs_root.mkdir()
            root_html = "".join(
                [
                    "<html><head><title>Home</title></head><body>",
                    '<a href="/docs/guide">Guide</a>',
                    '<a href="/docs/guide#fragment">Guide fragment</a>',
                    '<a href="/blog/post">Blog post</a>',
                    '<a href="https://outside.example/escape">Outside</a>',
                    "</body></html>",
                ]
            )
            guide_html = "".join(
                [
                    "<html><head><title>Guide</title></head><body>",
                    '<a href="/docs/guide/install">Install</a>',
                    '<a href="/docs/guide#fragment">Guide fragment</a>',
                    '<a href="/blog/post">Blog post</a>',
                    "</body></html>",
                ]
            )
            _ = (docs_root / "index.html").write_text(
                root_html,
                encoding="utf-8",
            )
            _ = (docs_root / "guide.html").write_text(guide_html, encoding="utf-8")
            _ = (docs_root / "install.html").write_text(
                "<html><head><title>Install</title></head><body>Install</body></html>",
                encoding="utf-8",
            )
            (root / "blog").mkdir()
            _ = (root / "blog" / "post.html").write_text(
                "<html><head><title>Blog</title></head><body>Blog</body></html>",
                encoding="utf-8",
            )

            routes = {
                "/docs": (docs_root / "index.html").read_bytes(),
                "/docs/guide": (docs_root / "guide.html").read_bytes(),
                "/docs/guide/install": (docs_root / "install.html").read_bytes(),
                "/blog/post": (root / "blog" / "post.html").read_bytes(),
            }

            with _serve_fixture(routes) as (base_url, requests), ExitStack() as stack:
                connection = sqlite3.connect(":memory:")
                _ = stack.callback(connection.close)
                store = SQLiteStore(connection)
                store.ensure_schema()
                source = Source(
                    source_id="source-1",
                    source_kind=SourceKind.WEB,
                    requested_locator=f"{base_url}/docs",
                    resolved_locator=f"{base_url}/docs",
                    canonical_locator=f"{base_url}/docs",
                    docset_root=f"{base_url}/docs",
                )
                store.upsert_source(source)

                client = httpx.Client(follow_redirects=True, timeout=5.0)
                _ = stack.callback(client.close)
                provider = WebDiscoveryProvider(client=client)
                engine = _RecordingIndexingEngine()
                orchestrator = RefreshOrchestrator(store, provider, engine)

                result = orchestrator.refresh_source("source-1")
                active_snapshot = store.get_active_snapshot("source-1")

                assert result.changed
                assert result.document_count == 3
                snapshot_id = result.snapshot_id
                assert snapshot_id is not None
                assert active_snapshot is not None
                assert active_snapshot.snapshot_id == snapshot_id
                assert set(requests) == {
                    "/docs",
                    "/docs/guide",
                    "/docs/guide/install",
                }
                assert len(requests) == 3
                assert engine.reindex_calls == [("source-1", snapshot_id, 3)]

                stored_documents = store.list_documents(snapshot_id)
                assert len(stored_documents) == 3
                assert {item.canonical_locator for item in stored_documents} == {
                    f"{base_url}/docs",
                    f"{base_url}/docs/guide",
                    f"{base_url}/docs/guide/install",
                }

    def test_refresh_keeps_github_management_pages_but_skips_chrome_and_repo_sibling_pages(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo_root = root / "repo"
            repo_root.mkdir()

            root_html = "".join(
                [
                    "<html><head><title>Repo</title></head><body>",
                    '<a href="/repo/collections">Collections</a>',
                    '<a href="/repo/search?l=css">Search CSS</a>',
                    '<a href="/repo/marketplace">Marketplace</a>',
                    '<a href="/repo/releases">Releases</a>',
                    '<a href="/repo/issues">Issues</a>',
                    '<a href="/repo/pulls">Pulls</a>',
                    '<a href="/repo/compare/main...HEAD">Compare</a>',
                    '<a href="/repo/blob/main/README.md">README</a>',
                    '<a href="/repo/wiki">Wiki</a>',
                    '<a href="/repo/tree/main/docs/guide.md">Docs</a>',
                    '<a href="/repo-foo/blob/main/README.md">Sibling</a>',
                    "</body></html>",
                ]
            )
            readme_html = "<html><head><title>README</title></head><body>install api</body></html>"
            wiki_html = (
                "<html><head><title>Wiki</title></head><body>how to use</body></html>"
            )
            docs_html = "<html><head><title>Docs</title></head><body>configuration</body></html>"
            collections_html = "<html><head><title>Collections</title></head><body>collections</body></html>"
            search_html = (
                "<html><head><title>Search</title></head><body>search</body></html>"
            )
            marketplace_html = "<html><head><title>Marketplace</title></head><body>marketplace</body></html>"
            releases_html = "<html><head><title>Releases</title></head><body>release notes</body></html>"
            issues_html = "<html><head><title>Issues</title></head><body>open issues</body></html>"
            pulls_html = "<html><head><title>Pulls</title></head><body>pull requests</body></html>"
            compare_html = "<html><head><title>Compare</title></head><body>compare versions</body></html>"
            sibling_html = "<html><head><title>Sibling</title></head><body>sibling repo</body></html>"

            _ = (repo_root / "index.html").write_text(root_html, encoding="utf-8")
            _ = (repo_root / "README.md").write_text(readme_html, encoding="utf-8")
            _ = (repo_root / "wiki").mkdir()
            _ = (repo_root / "wiki" / "index.html").write_text(
                wiki_html, encoding="utf-8"
            )
            _ = (repo_root / "tree").mkdir()
            _ = (repo_root / "tree" / "main").mkdir()
            _ = (repo_root / "tree" / "main" / "docs").mkdir(
                parents=True, exist_ok=True
            )
            _ = (repo_root / "tree" / "main" / "docs" / "guide.md").write_text(
                docs_html, encoding="utf-8"
            )
            _ = (repo_root / "releases").write_text(releases_html, encoding="utf-8")
            _ = (repo_root / "issues").write_text(issues_html, encoding="utf-8")
            _ = (repo_root / "pulls").write_text(pulls_html, encoding="utf-8")
            _ = (repo_root / "compare").mkdir()
            _ = (repo_root / "compare" / "main...HEAD").write_text(
                compare_html, encoding="utf-8"
            )
            sibling_root = root / "repo-foo"
            sibling_root.mkdir()
            _ = (sibling_root / "blob").mkdir()
            _ = (sibling_root / "blob" / "main").mkdir(parents=True, exist_ok=True)
            _ = (sibling_root / "blob" / "main" / "README.md").write_text(
                sibling_html, encoding="utf-8"
            )

            routes = {
                "/repo": (repo_root / "index.html").read_bytes(),
                "/repo/collections": collections_html.encode("utf-8"),
                "/repo/search?l=css": search_html.encode("utf-8"),
                "/repo/marketplace": marketplace_html.encode("utf-8"),
                "/repo/releases": releases_html.encode("utf-8"),
                "/repo/issues": issues_html.encode("utf-8"),
                "/repo/pulls": pulls_html.encode("utf-8"),
                "/repo/compare/main...HEAD": compare_html.encode("utf-8"),
                "/repo/blob/main/README.md": (repo_root / "README.md").read_bytes(),
                "/repo/wiki": (repo_root / "wiki" / "index.html").read_bytes(),
                "/repo/tree/main/docs/guide.md": (
                    repo_root / "tree" / "main" / "docs" / "guide.md"
                ).read_bytes(),
                "/repo-foo/blob/main/README.md": (
                    sibling_root / "blob" / "main" / "README.md"
                ).read_bytes(),
            }

            with _serve_fixture(routes) as (base_url, requests), ExitStack() as stack:
                connection = sqlite3.connect(":memory:")
                _ = stack.callback(connection.close)
                store = SQLiteStore(connection)
                store.ensure_schema()
                source = Source(
                    source_id="source-1",
                    source_kind=SourceKind.WEB,
                    requested_locator=f"{base_url}/repo",
                    resolved_locator=f"{base_url}/repo",
                    canonical_locator=f"{base_url}/repo",
                    docset_root=f"{base_url}/repo",
                )
                store.upsert_source(source)

                client = httpx.Client(follow_redirects=True, timeout=5.0)
                _ = stack.callback(client.close)
                provider = WebDiscoveryProvider(client=client)
                engine = _RecordingIndexingEngine()
                orchestrator = RefreshOrchestrator(store, provider, engine)

                result = orchestrator.refresh_source("source-1")
                active_snapshot = store.get_active_snapshot("source-1")

                assert result.changed
                assert result.document_count == 8
                snapshot_id = result.snapshot_id
                assert snapshot_id is not None
                assert active_snapshot is not None
                assert active_snapshot.snapshot_id == snapshot_id
                assert set(requests) == {
                    "/repo",
                    "/repo/blob/main/README.md",
                    "/repo/wiki",
                    "/repo/tree/main/docs/guide.md",
                    "/repo/compare/main...HEAD",
                    "/repo/issues",
                    "/repo/pulls",
                    "/repo/releases",
                }
                assert len(requests) == 8
                assert engine.reindex_calls == [("source-1", snapshot_id, 8)]

                stored_documents = store.list_documents(snapshot_id)
                assert len(stored_documents) == 8
                assert {item.canonical_locator for item in stored_documents} == {
                    f"{base_url}/repo",
                    f"{base_url}/repo/blob/main/README.md",
                    f"{base_url}/repo/wiki",
                    f"{base_url}/repo/tree/main/docs/guide.md",
                    f"{base_url}/repo/compare/main...HEAD",
                    f"{base_url}/repo/issues",
                    f"{base_url}/repo/pulls",
                    f"{base_url}/repo/releases",
                }

    def test_seed_counts_toward_max_pages(self) -> None:
        ordered = filter_and_order_discovered_documents(
            _source(),
            [
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs",
                    resolved_locator="https://docs.example.com/docs",
                    canonical_locator="https://docs.example.com/docs",
                ),
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide",
                    resolved_locator="https://docs.example.com/docs/guide",
                    canonical_locator="https://docs.example.com/docs/guide",
                ),
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/docs/guide/install",
                    resolved_locator="https://docs.example.com/docs/guide/install",
                    canonical_locator="https://docs.example.com/docs/guide/install",
                ),
                DiscoveredDocument(
                    requested_locator="https://docs.example.com/blog/post",
                    resolved_locator="https://docs.example.com/blog/post",
                    canonical_locator="https://docs.example.com/blog/post",
                ),
            ],
        )

        assert [item.canonical_locator for item in ordered] == [
            "https://docs.example.com/docs",
            "https://docs.example.com/docs/guide",
            "https://docs.example.com/docs/guide/install",
        ]
        assert [item.canonical_locator for item in ordered[:2]] == [
            "https://docs.example.com/docs",
            "https://docs.example.com/docs/guide",
        ]

    def test_repeat_runs_keep_the_same_order(self) -> None:
        candidates = [
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs",
                resolved_locator="https://docs.example.com/docs",
                canonical_locator="https://docs.example.com/docs",
            ),
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/guide",
                resolved_locator="https://docs.example.com/docs/guide",
                canonical_locator="https://docs.example.com/docs/guide",
            ),
            DiscoveredDocument(
                requested_locator="https://docs.example.com/docs/guide/install",
                resolved_locator="https://docs.example.com/docs/guide/install",
                canonical_locator="https://docs.example.com/docs/guide/install",
            ),
        ]

        first = filter_and_order_discovered_documents(_source(), candidates)
        second = filter_and_order_discovered_documents(_source(), candidates)

        assert [item.canonical_locator for item in first] == [
            item.canonical_locator for item in second
        ]

    def test_refresh_rejects_host_level_github_chrome_pages(self) -> None:
        with tempfile.TemporaryDirectory():
            routes = {
                "/code-yeongyu/oh-my-openagent": b'<html><head><title>Repo</title></head><body><h1>Oh My OpenAgent</h1><p>Local docs and prompts.</p><a href="/code-yeongyu/oh-my-openagent/blob/main/README.md">README</a><a href="/collections">Collections</a><a href="/mcp">MCP</a></body></html>',
                "/code-yeongyu/oh-my-openagent/blob/main/README.md": b"<html><head><title>README</title></head><body><h1>README</h1><p>Prometheus planning and start-work.</p></body></html>",
                "/collections": b'<html><head><title>Collections</title></head><body><a href="/mcp">MCP</a><a href="/marketplace">Marketplace</a><a href="/pricing">Pricing</a></body></html>',
                "/mcp": b'<html><head><title>MCP</title></head><body><a href="/marketplace">Marketplace</a><a href="/pricing">Pricing</a><a href="/login">Login</a></body></html>',
            }

            with _serve_fixture(routes) as (base_url, _requests), ExitStack() as stack:
                connection = sqlite3.connect(":memory:")
                _ = stack.callback(connection.close)
                store = SQLiteStore(connection)
                store.ensure_schema()
                source = Source(
                    source_id="source-1",
                    source_kind=SourceKind.WEB,
                    requested_locator=f"{base_url}/code-yeongyu/oh-my-openagent",
                    resolved_locator=f"{base_url}/code-yeongyu/oh-my-openagent",
                    canonical_locator=f"{base_url}/code-yeongyu/oh-my-openagent",
                    docset_root=f"{base_url}/code-yeongyu/oh-my-openagent",
                )
                store.upsert_source(source)

                client = httpx.Client(follow_redirects=True, timeout=5.0)
                _ = stack.callback(client.close)
                provider = WebDiscoveryProvider(client=client)
                engine = _RecordingIndexingEngine()
                orchestrator = RefreshOrchestrator(store, provider, engine)

                result = orchestrator.refresh_source("source-1")
                snapshot_id = result.snapshot_id
                assert snapshot_id is not None
                stored_documents = store.list_documents(snapshot_id)

                assert [item.canonical_locator for item in stored_documents] == [
                    f"{base_url}/code-yeongyu/oh-my-openagent",
                    f"{base_url}/code-yeongyu/oh-my-openagent/blob/main/README.md",
                ]

    def test_refresh_rejects_unrelated_pages_for_article_leaf_roots(self) -> None:
        with tempfile.TemporaryDirectory():
            routes = {
                "/blog/post": b'<html><head><title>Post</title></head><body><h1>Post</h1><p>Local article.</p><a href="/blog/post/comments">Comments</a><a href="/blog/archive">Archive</a><a href="/docs/guide">Docs guide</a></body></html>',
                "/blog/post/comments": b"<html><head><title>Comments</title></head><body><h1>Comments</h1><p>Replies.</p></body></html>",
                "/blog/archive": b"<html><head><title>Archive</title></head><body><h1>Archive</h1></body></html>",
                "/docs/guide": b"<html><head><title>Guide</title></head><body><h1>Guide</h1></body></html>",
            }

            with _serve_fixture(routes) as (base_url, requests), ExitStack() as stack:
                connection = sqlite3.connect(":memory:")
                _ = stack.callback(connection.close)
                store = SQLiteStore(connection)
                store.ensure_schema()
                source = Source(
                    source_id="source-1",
                    source_kind=SourceKind.WEB,
                    requested_locator=f"{base_url}/blog/post",
                    resolved_locator=f"{base_url}/blog/post",
                    canonical_locator=f"{base_url}/blog/post",
                    docset_root=f"{base_url}/blog/post",
                )
                store.upsert_source(source)

                client = httpx.Client(follow_redirects=True, timeout=5.0)
                _ = stack.callback(client.close)
                provider = WebDiscoveryProvider(client=client)
                engine = _RecordingIndexingEngine()
                orchestrator = RefreshOrchestrator(store, provider, engine)

                result = orchestrator.refresh_source("source-1")
                snapshot_id = result.snapshot_id
                assert snapshot_id is not None

                stored_documents = store.list_documents(snapshot_id)

                assert requests == ["/blog/post", "/blog/post/comments"]
                assert result.document_count == 2
                assert [item.canonical_locator for item in stored_documents] == [
                    f"{base_url}/blog/post",
                    f"{base_url}/blog/post/comments",
                ]
