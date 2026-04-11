# Root AGENTS.md

This is the root AGENTS file for locontext. It defines repo-wide rules. Add child `AGENTS.md` files only when a subtree develops materially different conventions.

## Commands

```bash
# Setup
uv sync --group dev
uv run pre-commit install

# Quality
uv run ruff check src/locontext tests
uv run ruff format --check src/locontext tests
uv run ty check

# Tests
uv run pytest

# Verification
uv run python -m compileall src tests
uv run locontext --help
```

## Toolchain

- **Runtime**: Python 3.13+ managed by `uv`
- **CLI**: `click`
- **HTTP**: `httpx` (sync-first)
- **Type System**: `ty`
- **Lint/Format**: `ruff`
- **Test Runner**: `pytest`

## Structure

- `src/locontext/domain/` — lifecycle models and contracts
- `src/locontext/app/` — use-case orchestration
- `src/locontext/sources/` — source discovery and canonicalization logic
- `src/locontext/store/` — project-local SQLite state
- `src/locontext/cli/` — CLI adapter layer only
- `tests/` — unit and integration-style local verification
- `docs/adr/` — architectural decisions

## Always

- Execute repo tooling through `uv run`.
- Keep `locontext` Python-first, CLI-first, and local-first.
- Keep the future Rust replacement boundary limited to engine/query concerns.
- Keep business logic out of the CLI layer.
- Prefer stdlib/dataclasses/protocols in core layers unless a library clearly reduces real complexity.
- Keep tests local and deterministic by default.

## Ask First

- Adding or changing runtime dependencies in `pyproject.toml`.
- Introducing ORMs, async DB stacks, or full agent frameworks.
- Expanding product scope toward vault/wiki/Obsidian/server/telemetry features.
- Moving logic across the ADR-defined architecture boundaries.

## Never

- Turn the core engine into an MCP-first or agent-framework-first design.
- Add network-dependent tests to the default test loop.
- Put source lifecycle or refresh orchestration logic into CLI commands.
- Commit secrets, credentials, or `.env` files.

## Verification Matrix

| Scope | Verification Command |
| :--- | :--- |
| Docs / governance only | `uv run ruff check src/locontext tests` |
| CLI surface | `uv run locontext --help && uv run ruff check src/locontext tests && uv run ty check` |
| Source / refresh / store logic | `uv run pytest && uv run ty check && uv run ruff check src/locontext tests` |
| PR preflight | `uv run ruff check src/locontext tests && uv run ruff format --check src/locontext tests && uv run ty check && uv run pytest && uv run python -m compileall src tests` |

## Path Contract

- Root AGENTS is authoritative for the current repo size.
- Add child AGENTS only when a subtree develops local rules that would otherwise create repetition or ambiguity.
- Generated local state belongs under project-local paths, not repo-tracked source directories.
