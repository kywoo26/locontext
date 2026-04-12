from __future__ import annotations

import unittest
from typing import cast

from locontext.engine.sqlite_lexical import build_chunks_from_structure

_Block = dict[str, object]


class StructuredChunkingContractTest(unittest.TestCase):
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

        self.assertEqual([chunk.chunk_index for chunk in chunks], [0, 1])
        self.assertEqual(chunks[0].chunk_id, "doc-1-chunk-0")
        self.assertEqual(chunks[1].chunk_id, "doc-1-chunk-1")
        self.assertIn("Guide > Intro", chunks[0].text)
        self.assertIn("Alpha paragraph.", chunks[0].text)
        self.assertIn("Beta paragraph.", chunks[0].text)
        self.assertIn("Guide > Intro > Setup", chunks[1].text)
        self.assertIn("Gamma paragraph.", chunks[1].text)

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

        self.assertEqual(len(chunks), 1)
        self.assertIn("CLI > Flags", chunks[0].text)
        self.assertIn("--help", chunks[0].text)
        self.assertIn("--version", chunks[0].text)

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
            title="Guide",
            blocks=blocks,
            chunk_prefix="doc-3",
        )
        second = build_chunks_from_structure(
            title="Guide",
            blocks=blocks,
            chunk_prefix="doc-3",
        )

        self.assertEqual(
            [chunk.chunk_id for chunk in first], [chunk.chunk_id for chunk in second]
        )
        self.assertEqual(
            [chunk.text for chunk in first], [chunk.text for chunk in second]
        )


if __name__ == "__main__":
    _ = unittest.main()
