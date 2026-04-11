# ADR 0001 - Product Direction

## Status

Proposed

## Decision

Build locontext as a local-first docs/context engine, not a broad knowledge platform.

## Drivers

- External hosted context tools add quota risk.
- Server-side retrieval adds privacy and query-leakage concerns.
- Local retrieval reduces token spend and round-trip latency.
- The core product should stay maintainable for one developer.

## Initial scope

- Ingest docs
- Query docs
- List/status
- Remove/reindex
- Config init
- One agent-facing integration path

## Explicit non-goals for v1

- Obsidian sync
- Cross-vault retrieval
- Eval/telemetry stack
- Publishing/install workflows
- Broad multi-target installer support
