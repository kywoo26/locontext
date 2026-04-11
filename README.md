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

## Out of scope for v1

- Obsidian integration
- Cross-vault workflows
- Eval / telemetry
- Publishing / install marketplace flows
- Multi-agent target sprawl
