import importlib.util
import sys
from pathlib import Path
from typing import Protocol, cast


class _ValidationResultLike(Protocol):
    ok: bool
    errors: tuple[str, ...]


class _ValidatorModule(Protocol):
    def validate_commit_message(self, message: str) -> _ValidationResultLike: ...

    def validate_commit_subject(self, subject: str) -> list[str]: ...

    def validate_commit_body(self, body: str) -> list[str]: ...


def _load_validator_module() -> object:
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "check_commit_message.py"
    )
    spec = importlib.util.spec_from_file_location("check_commit_message", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("expected scripts/check_commit_message.py to be loadable")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = cast(_ValidatorModule, _load_validator_module())


def test_validate_commit_message_accepts_compliant_subject_and_body() -> None:
    message = (
        "fix(query): prefer readme over releases\n\n"
        "Why:\nGitHub repo sources ranked releases above README.\n\n"
        "Behavior:\nREADME/docs content now outranks management pages for repo-doc intent.\n\n"
        "Refs: #30\n"
    )

    result = MODULE.validate_commit_message(message)

    assert result.ok
    assert result.errors == ()


def test_validate_commit_subject_rejects_feat_without_scope() -> None:
    errors = MODULE.validate_commit_subject("feat: add governance hook")

    assert errors == ["Commit type `feat` requires a scope"]


def test_validate_commit_subject_rejects_trailing_period() -> None:
    errors = MODULE.validate_commit_subject("docs(docs): add rules.")

    assert errors == ["Commit subject must not end with a period"]


def test_validate_commit_body_rejects_banned_agent_markers() -> None:
    errors = MODULE.validate_commit_body(
        "Why:\nkeep it clean\n\nCo-authored-by: Bot <bot@example.com>\nUltraworked with Sisyphus\ncoworker\n"
    )

    assert errors == [
        "Commit message contains banned AI/agent marker: co-authored-by:",
        "Commit message contains banned AI/agent marker: ultraworked with",
        "Commit message contains banned AI/agent marker: coworker",
    ]
