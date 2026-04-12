from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module
from typing import Protocol, cast

import click

from .. import __version__
from ..app.refresh import RefreshOrchestrator
from ..app.sources import (
    get_source_status,
    list_source_status,
    list_sources,
    register_source,
    remove_source,
)
from ..domain.models import DiscoveredDocument, QueryHit, Source
from ..store.sqlite import SQLiteStore
from .runtime import open_runtime


@click.group(
    context_settings={"help_option_names": ["-h", "--help"]},
    no_args_is_help=True,
)
@click.version_option(__version__, "--version", message="%(version)s")
def main() -> None:
    """Local-first docs context engine."""
    return


@main.group()
def source() -> None:
    """Manage registered documentation sources."""


@source.command("add")
@click.argument("locator")
def source_add(locator: str) -> None:
    runtime = open_runtime()
    try:
        result = register_source(runtime.store, locator)
    finally:
        runtime.close()

    status = "created" if result.created else "existing"
    click.echo(f"{status} source: {result.source.source_id}")
    click.echo(f"canonical locator: {result.source.canonical_locator}")
    click.echo(f"docset root: {result.source.docset_root}")


@source.command("list")
def source_list() -> None:
    runtime = open_runtime()
    try:
        sources = list_sources(runtime.store)
    finally:
        runtime.close()

    if not sources:
        click.echo("No sources registered.")
        return

    for registered_source in sources:
        click.echo(
            f"{registered_source.source_id} {registered_source.canonical_locator} -> "
            + registered_source.docset_root
        )


@source.command("remove")
@click.argument("source_id")
def source_remove(source_id: str) -> None:
    """Remove a registered documentation source."""
    runtime = open_runtime()
    try:
        result = remove_source(runtime.store, source_id)
    finally:
        runtime.close()

    if result.removed:
        click.echo(f"removed source: {result.source_id}")
        return

    click.echo(f"source not found: {result.source_id}")


@source.command("refresh")
@click.argument("source_id")
def source_refresh(source_id: str) -> None:
    runtime = open_runtime()
    try:
        orchestrator = RefreshOrchestrator(runtime.store)
        result = orchestrator.refresh_source(source_id)
    finally:
        runtime.close()

    click.echo(f"refreshed source: {result.source_id}")
    click.echo(f"result: {'changed' if result.changed else 'unchanged'}")
    click.echo(f"active snapshot: {result.snapshot_id}")
    click.echo(f"documents: {result.document_count}")


class _NoDiscoveryProvider:
    def discover(self, source: Source) -> Sequence[DiscoveredDocument]:
        _ = source
        raise RuntimeError("source reindex does not perform discovery")


class _QueryModule(Protocol):
    def query_local(
        self,
        store: SQLiteStore,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> list[QueryHit]: ...


@source.command("status")
def source_status() -> None:
    runtime = open_runtime()
    try:
        statuses = list_source_status(runtime.store)
    finally:
        runtime.close()

    if not statuses:
        click.echo("No sources registered.")
        return

    for status in statuses:
        snapshot_id = status.active_snapshot_id or "none"
        snapshot_status = (
            status.snapshot_status.value
            if status.snapshot_status is not None
            else "none"
        )
        fetched_at = status.fetched_at or "none"
        line = (
            f"{status.source_id} {status.canonical_locator} snapshot={snapshot_id} "
            f"status={snapshot_status} documents={status.document_count} "
            f"chunks={status.chunk_count} fetched_at={fetched_at}"
        )
        click.echo(line)


@source.command("show")
@click.argument("source_id")
def source_show(source_id: str) -> None:
    runtime = open_runtime()
    try:
        status = get_source_status(runtime.store, source_id)
    finally:
        runtime.close()

    if status is None:
        click.echo(f"source not found: {source_id}")
        return

    click.echo(f"source_id: {status.source_id}")
    click.echo(f"canonical_locator: {status.canonical_locator}")
    click.echo(f"docset_root: {status.docset_root}")
    click.echo(f"active_snapshot_id: {status.active_snapshot_id or 'none'}")
    click.echo(
        f"snapshot_status: {status.snapshot_status.value if status.snapshot_status is not None else 'none'}"
    )
    click.echo(f"document_count: {status.document_count}")
    click.echo(f"chunk_count: {status.chunk_count}")
    click.echo(f"fetched_at: {status.fetched_at or 'none'}")
    click.echo(f"etag: {status.etag or 'none'}")
    click.echo(f"last_modified: {status.last_modified or 'none'}")


@source.command("reindex")
@click.argument("source_id")
def source_reindex(source_id: str) -> None:
    runtime = open_runtime()
    try:
        orchestrator = RefreshOrchestrator(runtime.store, _NoDiscoveryProvider())
        result = orchestrator.reindex_source(source_id)
    finally:
        runtime.close()

    click.echo(f"reindexed source: {result.source_id}")
    click.echo(f"active snapshot: {result.snapshot_id}")
    click.echo(f"documents: {result.document_count}")


@main.command()
@click.argument("text", nargs=-1)
@click.option("--limit", default=5, show_default=True, type=click.IntRange(min=1))
@click.option("--source", "source_id", type=str)
def query(text: Sequence[str], limit: int, source_id: str | None) -> None:
    query_text = " ".join(text).strip()
    if not query_text:
        raise click.UsageError("Missing query text.")

    runtime = open_runtime()
    try:
        module = cast(_QueryModule, cast(object, import_module("locontext.app.query")))
        hits = module.query_local(
            runtime.store, query_text, limit=limit, source_id=source_id
        )
        source_cache: dict[str, str] = {}
        document_cache: dict[str, dict[str, str]] = {}
        for hit in hits:
            if hit.source_id not in source_cache:
                source = runtime.store.get_source(hit.source_id)
                source_cache[hit.source_id] = (
                    source.canonical_locator if source is not None else hit.source_id
                )
            if hit.snapshot_id not in document_cache:
                document_cache[hit.snapshot_id] = {
                    document.document_id: document.canonical_locator
                    for document in runtime.store.list_documents(hit.snapshot_id)
                }
    finally:
        runtime.close()

    if not hits:
        click.echo("No query results.")
        return

    for index, hit in enumerate(hits, start=1):
        source_locator = source_cache[hit.source_id]
        document_locator = document_cache.get(hit.snapshot_id, {}).get(hit.document_id)
        if document_locator is None:
            document_locator = hit.document_id
        click.echo(f"{index}. {source_locator}")
        click.echo(f"   document: {document_locator}")
        section_path = hit.metadata.get("section_path")
        if isinstance(section_path, list) and section_path:
            section = " > ".join(str(part) for part in cast(list[object], section_path))
        else:
            section = "none"
        click.echo(f"   section: {section}")
        click.echo(f"   snippet: {_build_snippet(hit.text, query_text)}")


def _build_snippet(text: str, query_text: str, *, max_chars: int = 160) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    terms = [term for term in query_text.split() if term]
    lower = normalized.lower()
    start = 0
    for term in terms:
        index = lower.find(term.lower())
        if index != -1:
            start = max(index - 20, 0)
            break
    end = min(start + max_chars, len(normalized))
    snippet = normalized[start:end].strip()
    if start > 0:
        snippet = f"...{snippet}"
    if end < len(normalized):
        snippet = f"{snippet}..."
    return snippet


if __name__ == "__main__":
    main()
