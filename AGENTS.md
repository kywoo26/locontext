# Root AGENTS.md

This is the root AGENTS file for locontext. It defines repo-wide rules. Add child `AGENTS.md` files only when a subtree develops materially different conventions.

## Toolchain

- **Runtime**: Python 3.13+ managed by `uv`
- **CLI**: `click`
- **HTTP**: `httpx` (sync-first)
- **Type System**: `ty`
- **Lint/Format**: `ruff`
- **Test Runner**: `pytest`

## Always

- Execute repo tooling through `uv run`.
- Keep the future Rust replacement boundary limited to engine/query concerns.
- Keep business logic out of the CLI layer.
- Prefer stdlib/dataclasses/protocols in core layers unless a library clearly reduces real complexity.
- Keep tests local and deterministic by default.
- Treat `uv run pytest` as the fast unit-test loop (covering `tests/unit/`); run integration tests explicitly with `uv run pytest --override-ini addopts="-ra --import-mode=importlib" -m integration` (covering `tests/integration/`) before opening a PR.
- Use integration tests for real heavy engines, subprocess/thread/server lifecycle, real network or DB services, benchmark-sized fixtures, or timing-sensitive behavior.

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
- Add agent co-author markers (e.g., `Co-authored-by:`, `Ultraworked with`) to commits.

## Verification Matrix

| Scope | Verification Command |
| :--- | :--- |
| Docs / governance only | `uv run ruff check src/locontext tests` |
| CLI surface | `uv run locontext --help && uv run ruff check src/locontext tests && uv run ty check` |
| Source / refresh / store logic | `uv run pytest && uv run ty check && uv run ruff check src/locontext tests` |
| Tests / fixtures | `uv run pytest && uv run ruff check src/locontext tests` |
| Integration check | `uv run pytest --override-ini addopts="-ra --import-mode=importlib" -m integration` |
| PR preflight | `uv run ruff check src/locontext tests && uv run ruff format --check src/locontext tests && uv run ty check && uv run pytest && uv run pytest --override-ini addopts="-ra --import-mode=importlib" -m integration` |

## Ownership

| Path | Role | Governance Owner |
| :--- | :--- | :--- |
| `src/locontext/` | Runtime code | Root `AGENTS.md` |
| `tests/unit/` | Unit tests | Root `AGENTS.md` |
| `tests/integration/` | Integration tests | Root `AGENTS.md` |
| `.github/` | CI / repo workflow surface | Root `AGENTS.md` |
| `docs/adr/` | Architecture contracts | Root `AGENTS.md` |

## PR Discipline

- Maintain atomic commits by concern.
- Use `type(scope): short imperative subject` for commit titles.
- Keep commit bodies focused on why/behavior/refs when the change is non-trivial.
- Run the `PR preflight` verification matrix command before opening.
- Reference issues in the footer if applicable: `Refs: #N` or `Fixes: #N`.

## Branch Naming

Use `type/description` where type matches the intent:
`feat/`, `fix/`, `docs/`, `refactor/`, `test/`, `ci/`, `deps/`

## Path Contract

- Root AGENTS is authoritative for the current repo size.
- Add child AGENTS only when a subtree develops local rules that would otherwise create repetition or ambiguity.
- Generated local state belongs under project-local paths, not repo-tracked source directories.
