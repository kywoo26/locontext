from __future__ import annotations

import json
from collections.abc import Sequence
from importlib import import_module
from typing import Protocol, cast

import click

from .. import __version__
from ..app.refresh import RefreshOrchestrator
from ..app.sources import (
    create_source_set,
    get_source_set,
    get_source_status,
    list_source_sets,
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


@main.group("source-set")
def source_set() -> None:
    """Manage named source sets."""


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
    click.echo(f"freshness: {result.freshness_state}")
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

    def query_local_json(
        self,
        store: SQLiteStore,
        text: str,
        *,
        limit: int,
        source_id: str | None = None,
    ) -> _QueryEnvelope: ...


class _QueryEnvelopeHit(Protocol):
    rank: int
    source_locator: str
    document_locator: str
    section_path: list[str]
    snippet: str


class _QueryEnvelope(Protocol):
    hit_count: int
    hits: list[_QueryEnvelopeHit]

    def as_dict(self) -> dict[str, object]: ...


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
            f"chunks={status.chunk_count} fetched_at={fetched_at} freshness={status.freshness_state}"
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
    click.echo(f"freshness: {status.freshness_state}")
    click.echo(f"freshness_reason: {status.freshness_reason}")
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


@source_set.command("add")
@click.argument("set_name")
@click.argument("source_ids", nargs=-1)
def source_set_add(set_name: str, source_ids: tuple[str, ...]) -> None:
    if not source_ids:
        raise click.UsageError("Missing source IDs.")

    runtime = open_runtime()
    try:
        try:
            result = create_source_set(runtime.store, set_name, list(source_ids))
        except KeyError as exc:
            click.echo(exc.args[0] if exc.args else str(exc))
            return
    finally:
        runtime.close()

    status = "created" if result.created else "updated"
    click.echo(f"{status} source set: {result.source_set.set_name}")
    click.echo(
        "source_ids: "
        + ", ".join(member.source_id for member in result.source_set.members)
    )


@source_set.command("list")
def source_set_list() -> None:
    runtime = open_runtime()
    try:
        source_sets = list_source_sets(runtime.store)
    finally:
        runtime.close()

    if not source_sets:
        click.echo("No source sets registered.")
        return

    for index, source_set_result in enumerate(source_sets):
        if index > 0:
            click.echo("")
        click.echo(f"set_name: {source_set_result.set_name}")
        click.echo(
            "source_ids: "
            + ", ".join(member.source_id for member in source_set_result.members)
        )


@source_set.command("show")
@click.argument("set_name")
def source_set_show(set_name: str) -> None:
    runtime = open_runtime()
    try:
        source_set_result = get_source_set(runtime.store, set_name)
    finally:
        runtime.close()

    if source_set_result is None:
        click.echo(f"source set not found: {set_name}")
        return

    click.echo(f"set_name: {source_set_result.set_name}")
    click.echo(f"member_count: {len(source_set_result.members)}")
    click.echo("members:")
    for member in source_set_result.members:
        click.echo(
            f"  - [{member.member_index}] {member.source_id} {member.canonical_locator}"
        )


@main.command()
@click.argument("text", nargs=-1)
@click.option("--limit", default=5, show_default=True, type=click.IntRange(min=1))
@click.option("--source", "source_id", type=str)
@click.option("--json", "json_output", is_flag=True)
def query(
    text: Sequence[str],
    limit: int,
    source_id: str | None,
    json_output: bool,
) -> None:
    query_text = " ".join(text).strip()
    if not query_text:
        raise click.UsageError("Missing query text.")

    runtime = open_runtime()
    try:
        module = cast(_QueryModule, cast(object, import_module("locontext.app.query")))
        payload = module.query_local_json(
            runtime.store, query_text, limit=limit, source_id=source_id
        )
    finally:
        runtime.close()

    if json_output:
        click.echo(json.dumps(payload.as_dict(), separators=(",", ":")))
        return

    if payload.hit_count == 0:
        click.echo("No query results.")
        return

    for hit in payload.hits:
        click.echo(f"{hit.rank}. {hit.source_locator}")
        click.echo(f"   document: {hit.document_locator}")
        section = " > ".join(hit.section_path) if hit.section_path else "none"
        click.echo(f"   section: {section}")
        click.echo(f"   snippet: {hit.snippet}")


if __name__ == "__main__":
    main()
