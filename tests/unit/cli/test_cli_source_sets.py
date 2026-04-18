from click.testing import CliRunner

from locontext.cli.main import main


def _add_source(runner: CliRunner, locator: str) -> str:
    result = runner.invoke(main, ["source", "add", locator])
    assert result.exit_code == 0
    return result.output.splitlines()[0].split()[-1]


def test_source_set_add_reports_created_set(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        alpha_id = _add_source(runner, "https://docs.example.com/alpha")
        beta_id = _add_source(runner, "https://docs.example.com/beta")
        result = runner.invoke(main, ["source-set", "add", "docs", alpha_id, beta_id])
        assert result.exit_code == 0
        assert (
            result.output
            == "created source set: docs\n" + f"source_ids: {alpha_id}, {beta_id}\n"
        )


def test_source_set_add_reports_missing_sources_without_error(
    runner: CliRunner,
) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source-set", "add", "docs", "missing-id"])
        assert result.exit_code == 0
        assert result.output == "Sources not found for source set 'docs': missing-id\n"


def test_source_set_list_reports_empty_state(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source-set", "list"])
        assert result.exit_code == 0
        assert result.output == "No source sets registered.\n"


def test_source_set_list_shows_sets_in_stable_order(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        alpha_id = _add_source(runner, "https://docs.example.com/alpha")
        beta_id = _add_source(runner, "https://docs.example.com/beta")
        _ = runner.invoke(main, ["source-set", "add", "zeta", beta_id])
        _ = runner.invoke(main, ["source-set", "add", "alpha", alpha_id])
        result = runner.invoke(main, ["source-set", "list"])
        assert result.exit_code == 0
        assert (
            result.output
            == "set_name: alpha\n"
            + f"source_ids: {alpha_id}\n"
            + "\n"
            + "set_name: zeta\n"
            + f"source_ids: {beta_id}\n"
        )


def test_source_set_show_reports_missing_set_without_error(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source-set", "show", "docs"])
        assert result.exit_code == 0
        assert result.output == "source set not found: docs\n"


def test_source_set_show_renders_members_deterministically(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        alpha_id = _add_source(runner, "https://docs.example.com/alpha")
        beta_id = _add_source(runner, "https://docs.example.com/beta")
        _ = runner.invoke(main, ["source-set", "add", "docs", alpha_id, beta_id])
        result = runner.invoke(main, ["source-set", "show", "docs"])
        assert result.exit_code == 0
        assert (
            result.output
            == "set_name: docs\n"
            + "member_count: 2\n"
            + "members:\n"
            + f"  - [0] {alpha_id} https://docs.example.com/alpha\n"
            + f"  - [1] {beta_id} https://docs.example.com/beta\n"
        )


def test_source_set_help_works(runner: CliRunner) -> None:
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["source-set", "--help"])
        assert result.exit_code == 0
        assert "Manage named source sets." in result.output
