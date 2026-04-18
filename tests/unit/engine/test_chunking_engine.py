from typing import cast

from locontext.engine.sqlite_lexical import build_chunks_from_structure

_Block = dict[str, object]


class TestStructuredChunkingContract:
    def test_heading_and_paragraphs_form_multiple_chunks(self) -> None:
        chunks = build_chunks_from_structure(
            title="Guide",
            blocks=cast(
                tuple[_Block, ...],
                (
                    {"kind": "heading", "level": 1, "text": "Intro"},
                    {"kind": "paragraph", "text": "Alpha paragraph."},
                    {"kind": "paragraph", "text": "Beta paragraph."},
                    {"kind": "heading", "level": 2, "text": "Setup"},
                    {"kind": "paragraph", "text": "Gamma paragraph."},
                ),
            ),
            chunk_prefix="doc-1",
        )
        assert [chunk.chunk_index for chunk in chunks] == [0, 1]
        assert chunks[0].chunk_id == "doc-1-chunk-0"
        assert chunks[1].chunk_id == "doc-1-chunk-1"
        assert "Guide > Intro" in chunks[0].text
        assert "Alpha paragraph." in chunks[0].text
        assert "Beta paragraph." in chunks[0].text
        assert "Guide > Intro > Setup" in chunks[1].text
        assert "Gamma paragraph." in chunks[1].text

    def test_list_items_group_under_same_section(self) -> None:
        chunks = build_chunks_from_structure(
            title="CLI",
            blocks=cast(
                tuple[_Block, ...],
                (
                    {"kind": "heading", "level": 1, "text": "Flags"},
                    {"kind": "list_item", "text": "--help"},
                    {"kind": "list_item", "text": "--version"},
                ),
            ),
            chunk_prefix="doc-2",
        )
        assert len(chunks) == 1
        assert "CLI > Flags" in chunks[0].text
        assert "--help" in chunks[0].text
        assert "--version" in chunks[0].text

    def test_chunk_ids_are_stable_for_same_input(self) -> None:
        blocks = cast(
            tuple[_Block, ...],
            (
                {"kind": "heading", "level": 1, "text": "Intro"},
                {"kind": "paragraph", "text": "Stable content."},
                {"kind": "heading", "level": 2, "text": "Next"},
                {"kind": "paragraph", "text": "More stable content."},
            ),
        )
        first = build_chunks_from_structure(
            title="Guide", blocks=blocks, chunk_prefix="doc-3"
        )
        second = build_chunks_from_structure(
            title="Guide", blocks=blocks, chunk_prefix="doc-3"
        )
        assert [chunk.chunk_id for chunk in first] == [
            chunk.chunk_id for chunk in second
        ]
        assert [chunk.text for chunk in first] == [chunk.text for chunk in second]
