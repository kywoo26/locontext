import pytest

from locontext.app.sources import create_source_set, get_source_set, list_source_sets
from locontext.domain.models import Source, SourceKind
from locontext.store.sqlite import SQLiteStore


def _seed_source(store: SQLiteStore, source_id: str, canonical_locator: str) -> None:
    store.upsert_source(
        Source(
            source_id=source_id,
            source_kind=SourceKind.WEB,
            requested_locator=canonical_locator,
            resolved_locator=canonical_locator,
            canonical_locator=canonical_locator,
            docset_root="https://docs.example.com",
        )
    )


def test_create_source_set_collapses_duplicate_source_ids(store: SQLiteStore) -> None:
    _seed_source(store, "source-alpha", "https://docs.example.com/alpha")
    _seed_source(store, "source-beta", "https://docs.example.com/beta")
    result = create_source_set(
        store,
        "docs",
        ["source-beta", "source-alpha", "source-beta", "source-beta"],
    )
    assert result.created
    assert result.duplicate_source_ids == ("source-beta", "source-beta")
    assert [
        (member.source_id, member.canonical_locator, member.member_index)
        for member in result.source_set.members
    ] == [
        ("source-beta", "https://docs.example.com/beta", 0),
        ("source-alpha", "https://docs.example.com/alpha", 1),
    ]
    loaded = get_source_set(store, "docs")
    assert loaded is not None
    assert loaded == result.source_set


def test_create_source_set_reuses_existing_named_set(store: SQLiteStore) -> None:
    _seed_source(store, "source-alpha", "https://docs.example.com/alpha")
    _seed_source(store, "source-beta", "https://docs.example.com/beta")
    first = create_source_set(store, "docs", ["source-alpha"])
    second = create_source_set(store, "docs", ["source-beta", "source-alpha"])
    assert first.created
    assert not second.created
    assert first.source_set.source_set_id == second.source_set.source_set_id
    assert [member.source_id for member in second.source_set.members] == [
        "source-beta",
        "source-alpha",
    ]


def test_create_source_set_requires_all_sources_to_exist(store: SQLiteStore) -> None:
    _seed_source(store, "source-present", "https://docs.example.com/present")
    with pytest.raises(KeyError, match="source-missing"):
        _ = create_source_set(store, "docs", ["source-present", "source-missing"])
    assert list_source_sets(store) == []
    assert store.get_source_set("docs") is None


def test_list_source_sets_is_sorted_by_name(store: SQLiteStore) -> None:
    _seed_source(store, "source-alpha", "https://docs.example.com/alpha")
    _seed_source(store, "source-beta", "https://docs.example.com/beta")
    _ = create_source_set(store, "zeta", ["source-beta"])
    _ = create_source_set(store, "alpha", ["source-alpha"])
    rows = list_source_sets(store)
    assert [source_set.set_name for source_set in rows] == ["alpha", "zeta"]
    assert [
        [member.source_id for member in source_set.members] for source_set in rows
    ] == [["source-alpha"], ["source-beta"]]
