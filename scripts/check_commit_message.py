#!/usr/bin/env python3
"""Validate commit messages against repo commit-message policy."""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ALLOWED_TYPES = {"feat", "fix", "refactor", "docs", "test", "ci", "deps"}
ALLOWED_SCOPES = {
    "cli",
    "sources",
    "store",
    "query",
    "domain",
    "app",
    "docs",
    "test",
    "ci",
    "deps",
}
TITLE_PATTERN = re.compile(
    r"^(?P<type>feat|fix|refactor|docs|test|ci|deps)(?:\((?P<scope>[a-z0-9-]+)\))?: (?P<subject>.+)$"
)
BANNED_MARKERS = (
    "co-authored-by:",
    "ultraworked with",
    "coworker",
)


@dataclass(frozen=True, slots=True)
class ValidationResult:
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_commit_subject(subject: str) -> list[str]:
    errors: list[str] = []
    cleaned = subject.strip()

    if not cleaned:
        return ["Commit subject is required"]

    if len(cleaned) > 72:
        errors.append(
            f"Commit subject is {len(cleaned)} characters; keep it to 72 characters or fewer"
        )

    match = TITLE_PATTERN.fullmatch(cleaned)
    if match is None:
        errors.append(
            "Commit subject must use `type(scope): subject` with an allowed type and scope"
        )
        return errors

    commit_type = match.group("type")
    scope = match.group("scope")

    if commit_type not in ALLOWED_TYPES:
        errors.append(f"Commit type `{commit_type}` is not allowed")

    if commit_type in {"feat", "fix"} and scope is None:
        errors.append(f"Commit type `{commit_type}` requires a scope")

    if scope is not None and scope not in ALLOWED_SCOPES:
        errors.append(f"Commit scope `{scope}` is not documented in repo policy")

    if cleaned.endswith("."):
        errors.append("Commit subject must not end with a period")

    return errors


def validate_commit_body(body: str) -> list[str]:
    lowered = body.lower()
    return [
        f"Commit message contains banned AI/agent marker: {marker}"
        for marker in BANNED_MARKERS
        if marker in lowered
    ]


def validate_commit_message(message: str) -> ValidationResult:
    lines = message.splitlines()
    subject = lines[0] if lines else ""
    body = "\n".join(lines[1:])
    errors = [*validate_commit_subject(subject), *validate_commit_body(body)]
    return ValidationResult(errors=tuple(errors))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("message_file", help="Path to commit message file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    message = Path(args.message_file).read_text(encoding="utf-8")
    result = validate_commit_message(message)
    if result.ok:
        return 0
    for error in result.errors:
        print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
