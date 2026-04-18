from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Protocol, cast


class _ValidationResultLike(Protocol):
    ok: bool
    errors: tuple[str, ...]


class _ValidatorModule(Protocol):
    def validate_pr_governance(
        self, title: str, body: str
    ) -> _ValidationResultLike: ...

    def validate_pr_title(self, title: str) -> list[str]: ...

    def validate_pr_body(self, body: str) -> list[str]: ...


def _load_validator_module() -> object:
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "check_pr_governance.py"
    )
    spec = importlib.util.spec_from_file_location("check_pr_governance", module_path)
    if spec is None or spec.loader is None:
        raise AssertionError("expected scripts/check_pr_governance.py to be loadable")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = cast(_ValidatorModule, _load_validator_module())


def test_validate_pr_governance_accepts_compliant_title_and_body() -> None:
    body = """
## Problem / Motivation
We need a local validator for PR metadata.

## Proposed Change
Add a pure script that validates PR titles and bodies.

## Alternatives Considered
Keep relying on templates only, which allows malformed metadata.

## Surfaces Touched
- [x] Docs / Governance

## Verification
- [x] `uv run pytest tests/unit/test_pr_governance_validator.py -q`

## Contract Sync
No contract sync is required for this validator-only change.

## Risks / Rollback
The change is isolated to the validator script and can be rolled back by removing it.
"""

    result = MODULE.validate_pr_governance(
        "test(ci): add PR governance validator",
        body,
    )

    assert result.ok
    assert result.errors == ()


def test_validate_pr_title_rejects_feat_without_scope() -> None:
    errors = MODULE.validate_pr_title("feat: add PR governance validator")

    assert errors == ["PR title type `feat` requires a scope"]


def test_validate_pr_body_rejects_missing_section() -> None:
    body = """
## Problem / Motivation
The repo needs a validator.

## Proposed Change
Add a validator for PR metadata.

## Alternatives Considered
Use only template comments.

## Surfaces Touched
- [x] Docs / Governance

## Verification
- [x] `uv run pytest tests/unit/test_pr_governance_validator.py -q`

## Contract Sync
No contract sync is required.
"""

    errors = MODULE.validate_pr_body(body)

    assert errors == ["PR body is missing required section: ## Risks / Rollback"]


def test_validate_pr_body_rejects_placeholder_only_section() -> None:
    body = """
## Problem / Motivation
<!-- Why this change? -->

## Proposed Change
<!-- What changes at the contract/surface level? -->

## Alternatives Considered
Skipped for trivial changes.

## Surfaces Touched
- [ ] CLI
- [ ] Docs / Governance

## Verification
<!-- Run the subset from AGENTS.md that matches your surfaces. -->

## Contract Sync
<!-- If you changed a surface, did you update its mirror? -->

## Risks / Rollback
<!-- Breaking changes? Migration notes? Performance regressions? -->
"""

    errors = MODULE.validate_pr_body(body)

    assert errors == [
        "PR body section `## Problem / Motivation` is blank or placeholder-only",
        "PR body section `## Proposed Change` is blank or placeholder-only",
        "PR body section `## Surfaces Touched` is blank or placeholder-only",
        "PR body section `## Verification` is blank or placeholder-only",
        "PR body section `## Contract Sync` is blank or placeholder-only",
        "PR body section `## Risks / Rollback` is blank or placeholder-only",
    ]


def test_validate_pr_title_accepts_governance_scope() -> None:
    errors = MODULE.validate_pr_title(
        "ci(governance): add local commit hook enforcement"
    )

    assert errors == []
