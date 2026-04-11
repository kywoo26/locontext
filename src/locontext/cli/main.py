from __future__ import annotations

from collections.abc import Sequence

import click

from .. import __version__
from ..app.refresh import RefreshOrchestrator
from ..app.sources import list_sources, register_source
from ..domain.models import DiscoveredDocument, Source
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


if __name__ == "__main__":
    main()
