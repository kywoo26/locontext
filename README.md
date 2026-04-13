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

## Bootstrap

```bash
uv run locontext init
uv run locontext status
```

## Out of scope for v1

- Obsidian integration
- Cross-vault workflows
- Eval / telemetry
- Publishing / install marketplace flows
- Multi-agent target sprawl
