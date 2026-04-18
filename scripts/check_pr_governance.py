#!/usr/bin/env python3
"""Validate PR metadata against repo governance policy.

The validator is pure: it accepts title/body text and returns human-readable
errors without touching GitHub APIs or repository state.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

ALLOWED_TITLE_TYPES = {"feat", "fix", "refactor", "docs", "test", "ci", "deps"}
ALLOWED_TITLE_SCOPES = {
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

REQUIRED_SECTION_HEADINGS = (
    "Problem / Motivation",
    "Proposed Change",
    "Alternatives Considered",
    "Surfaces Touched",
    "Verification",
    "Contract Sync",
    "Risks / Rollback",
)

TITLE_PATTERN = re.compile(
    r"^(?P<type>feat|fix|refactor|docs|test|ci|deps)(?:\((?P<scope>[a-z0-9-]+)\))?: (?P<subject>.+)$"
)
HEADING_PATTERN = re.compile(r"^##\s+(?P<heading>.+?)\s*$", re.MULTILINE)
HTML_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
CHECKBOX_PATTERN = re.compile(r"^[-*]\s+\[(?P<mark>[ xX])\]\s*(?P<text>.*)$")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def validate_pr_title(title: str) -> list[str]:
    errors: list[str] = []
    cleaned = title.strip()

    if not cleaned:
        return ["PR title is required"]

    if len(cleaned) > 72:
        errors.append(
            f"PR title is {len(cleaned)} characters; keep it to 72 characters or fewer"
        )

    match = TITLE_PATTERN.fullmatch(cleaned)
    if match is None:
        errors.append(
            "PR title must use `type(scope): subject` with an allowed type and scope"
        )
        return errors

    title_type = match.group("type")
    scope = match.group("scope")

    if title_type not in ALLOWED_TITLE_TYPES:
        errors.append(f"PR title type `{title_type}` is not allowed")

    if title_type in {"feat", "fix"} and scope is None:
        errors.append(f"PR title type `{title_type}` requires a scope")

    if scope is not None and scope not in ALLOWED_TITLE_SCOPES:
        errors.append(f"PR title scope `{scope}` is not documented in repo policy")

    if cleaned.endswith("."):
        errors.append("PR title must not end with a period")

    return errors


def _extract_sections(body: str) -> dict[str, str]:
    matches = list(HEADING_PATTERN.finditer(body))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        heading = match.group("heading").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        sections[heading] = body[start:end]

    return sections


def _section_has_meaningful_content(section_body: str) -> bool:
    cleaned = HTML_COMMENT_PATTERN.sub("", section_body)

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        checkbox = CHECKBOX_PATTERN.fullmatch(line)
        if checkbox is not None:
            if checkbox.group("mark").lower() == "x":
                return True
            continue

        return True

    return False


def validate_pr_body(body: str) -> list[str]:
    errors: list[str] = []
    sections = _extract_sections(body)

    for heading in REQUIRED_SECTION_HEADINGS:
        section_body = sections.get(heading)
        if section_body is None:
            errors.append(f"PR body is missing required section: ## {heading}")
            continue

        if not _section_has_meaningful_content(section_body):
            errors.append(
                f"PR body section `## {heading}` is blank or placeholder-only"
            )

    return errors


def validate_pr_governance(title: str, body: str) -> ValidationResult:
    errors = [*validate_pr_title(title), *validate_pr_body(body)]
    return ValidationResult(errors=tuple(errors))


def _read_body_from_args(args: argparse.Namespace) -> str:
    body = cast(str | None, getattr(args, "body", None))
    body_file = cast(str | None, getattr(args, "body_file", None))

    if body is not None:
        return body
    if body_file is not None:
        return Path(body_file).read_text(encoding="utf-8")
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument("--title", required=True, help="Pull request title")
    _ = parser.add_argument("--body", help="Pull request body")
    _ = parser.add_argument("--body-file", help="Read pull request body from a file")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    body = cast(str | None, getattr(args, "body", None))
    body_file = cast(str | None, getattr(args, "body_file", None))
    title = cast(str, args.title)

    if body is not None and body_file is not None:
        parser.error("use either --body or --body-file, not both")

    result = validate_pr_governance(title, _read_body_from_args(args))
    if result.ok:
        return 0

    for error in result.errors:
        print(error, file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
