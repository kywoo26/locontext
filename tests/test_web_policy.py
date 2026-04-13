from __future__ import annotations

import unittest

from locontext.sources.web.policy import WebPageSignals, decide_page_admission


class WebPolicyTest(unittest.TestCase):
    def test_rejects_navigation_chrome_like_page(self) -> None:
        decision = decide_page_admission(
            canonical_locator="https://github.com/collections",
            seed_locator="https://github.com/code-yeongyu/oh-my-openagent",
            signals=WebPageSignals(
                visible_text_chars=120,
                link_text_chars=420,
                paragraph_count=0,
                heading_count=0,
                path_depth=1,
            ),
        )

        self.assertFalse(decision.accepted)
        self.assertIn("link_density", decision.reasons)
        self.assertIn("seed_path_escape", decision.reasons)

    def test_accepts_content_rich_repo_like_page(self) -> None:
        decision = decide_page_admission(
            canonical_locator="https://github.com/code-yeongyu/oh-my-openagent",
            seed_locator="https://github.com/code-yeongyu/oh-my-openagent",
            signals=WebPageSignals(
                visible_text_chars=900,
                link_text_chars=120,
                paragraph_count=5,
                heading_count=3,
                path_depth=2,
            ),
        )

        self.assertTrue(decision.accepted)
        self.assertIn("content_rich", decision.reasons)

    def test_accepts_normal_docs_page(self) -> None:
        decision = decide_page_admission(
            canonical_locator="https://click.palletsprojects.com/en/stable/arguments",
            seed_locator="https://click.palletsprojects.com/en/stable/",
            signals=WebPageSignals(
                visible_text_chars=1100,
                link_text_chars=180,
                paragraph_count=7,
                heading_count=4,
                path_depth=2,
            ),
        )

        self.assertTrue(decision.accepted)


if __name__ == "__main__":
    _ = unittest.main()
