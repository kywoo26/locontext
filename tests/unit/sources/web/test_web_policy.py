from locontext.sources.web.policy import WebPageSignals, decide_page_admission


class TestWebPolicy:
    def test_accepts_github_repo_docs_surfaces_including_wiki(self) -> None:
        for canonical_locator in [
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/README.md",
            "https://github.com/code-yeongyu/oh-my-openagent/tree/main/docs/guide.md",
            "https://github.com/code-yeongyu/oh-my-openagent/wiki",
            "https://github.com/code-yeongyu/oh-my-openagent/blob/main/AGENTS.md",
            "https://github.com/code-yeongyu/oh-my-openagent/releases",
            "https://github.com/code-yeongyu/oh-my-openagent/issues",
            "https://github.com/code-yeongyu/oh-my-openagent/pulls",
            "https://github.com/code-yeongyu/oh-my-openagent/compare/main...HEAD",
        ]:
            decision = decide_page_admission(
                canonical_locator=canonical_locator,
                seed_locator="https://github.com/code-yeongyu/oh-my-openagent",
                signals=WebPageSignals(
                    visible_text_chars=900,
                    link_text_chars=120,
                    paragraph_count=5,
                    heading_count=3,
                    path_depth=2,
                ),
            )
            assert decision.accepted

    def test_rejects_github_repo_chrome_surfaces_even_with_rich_signals(self) -> None:
        for canonical_locator in [
            "https://github.com/code-yeongyu/oh-my-openagent/collections",
            "https://github.com/code-yeongyu/oh-my-openagent/search?q=agent",
            "https://github.com/code-yeongyu/oh-my-openagent/marketplace",
            "https://github.com/code-yeongyu/oh-my-openagent/pulse",
            "https://github.com/code-yeongyu/oh-my-openagent/insights",
            "https://github.com/code-yeongyu/oh-my-openagent/commits/main",
            "https://github.com/code-yeongyu/oh-my-openagent/tags",
        ]:
            decision = decide_page_admission(
                canonical_locator=canonical_locator,
                seed_locator="https://github.com/code-yeongyu/oh-my-openagent",
                signals=WebPageSignals(
                    visible_text_chars=900,
                    link_text_chars=120,
                    paragraph_count=5,
                    heading_count=3,
                    path_depth=2,
                ),
            )
            assert not decision.accepted

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
        assert not decision.accepted
        assert "link_density" in decision.reasons
        assert "seed_path_escape" in decision.reasons

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
        assert decision.accepted
        assert "content_rich" in decision.reasons

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
        assert decision.accepted
