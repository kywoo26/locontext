# locontext

Local-first context engine for docs grounding.

## Intent

- Avoid mandatory server round-trips for documentation lookup.
- Reduce quota dependence from hosted context providers.
- Improve privacy by keeping both documents and queries local-first.
- Preserve predictable, project-aware retrieval with lower token overhead.

## Direction

- Python-first v1 for speed of iteration.
- Clear engine boundary so indexing/query can move to Rust later without rewriting the whole app.
- Start narrow: ingest, query, list/status, remove, config, and one agent integration path.

## Current machine-facing path

- The first thin machine-facing path is `locontext query --json`.
- It stays local-only and transport-agnostic.
- Broader MCP or server transport remains deferred.

## Query quality baseline

- A dev-only baseline command is available via `python -m locontext.dev.eval_query_quality --fixture <name>`.
- It is intended for deterministic local regression checks, not end-user product surface.

## Live public-source smoke harness

- A dev-only smoke harness is available via `python -m locontext.dev.live_public_smoke --output-dir artifacts/live-public-smoke`.
- It measures refresh and query behavior against a curated set of public documentation sources.
- Results are captured in `report.json` and `run.log` within a timestamped run directory.
- A manual GitHub Actions workflow `live-public-smoke.yml` is available for running this harness in CI and retaining artifacts for evidence.
- Status vocabulary:
    - `pass`: Top hit is within the accepted locator set and no warning budget breach.
    - `warn`: Warning budget breached but top hit is still accepted.
    - `fail`: Source refresh failed, zero documents/hits, or top hit is not accepted.
- Success invariant: The harness uses accepted top locator sets per source to determine quality, rather than brittle exact snippet matching.

## Bootstrap

```bash
uv run locontext init
uv run locontext status
uv run locontext doctor
```

## Testing

```bash
# Run unit tests (fast loop)
uv run pytest

# Run integration tests (explicitly)
uv run pytest --override-ini addopts="-ra --import-mode=importlib" -m integration
```

## Out of scope for v1

- Obsidian integration
- Cross-vault workflows
- Eval / telemetry
- Publishing / install marketplace flows
- Multi-agent target sprawl
