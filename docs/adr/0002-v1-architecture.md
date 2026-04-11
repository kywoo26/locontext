# ADR 0002 - V1 Architecture

## Status

Proposed

## Decision

Build locontext v1 as a narrow, project-local, CLI-first docs/context engine.

The v1 architecture separates:

- source discovery, fetch, canonicalization, and extraction
- project-local state and metadata persistence
- indexing and query execution
- CLI and application orchestration

Refresh and update are core capabilities, not optional maintenance features.

The future Rust-replaceable boundary is limited to the indexing and query engine.

## Drivers

- Local-first and privacy-preserving behavior
- Independence from hosted docs/context providers
- Deterministic, inspectable project-local state
- Refresh and update as first-class product behavior
- Low operational overhead for a solo maintainer
- Clear future boundary for a Rust engine replacement
- Narrow v1 scope with minimal product surface

## Architecture shape

- `cli/` for command entrypoints only
- `app/` for use-case orchestration
- `domain/` for lifecycle models and engine-facing contracts
- `sources/` for discovery, fetch, normalization, and extraction
- `store/` for SQLite-backed project-local state
- `engine/` for indexing and query implementation

## Boundary rule

The following stay outside the future Rust boundary:

- CLI
- configuration and project paths
- source registration
- discovery and fetch
- canonicalization and extraction
- refresh orchestration
- persistence of source and snapshot state

The Rust-replaceable boundary applies only to engine operations such as:

- upserting documents and chunks into the local index
- deleting indexed content for a source or snapshot
- searching ranked hits
- reporting index statistics

## V1 scope

V1 is centered on a single project-local docs retrieval lifecycle:

- register a source
- discover and fetch docs
- normalize and chunk content
- index local content
- query local content
- refresh an existing source
- remove a source and its local state

## Explicit non-goals

- vault or wiki productization
- Obsidian integration
- cross-vault or cross-project knowledge workflows
- eval or telemetry systems
- hosted sync, accounts, or remote services
- plugin or installer matrices
- transport-first design driven by MCP

## Consequences

### Positive

- Keeps v1 centered on the real retrieval product
- Makes refresh behavior part of the core architecture
- Preserves a clean migration path to a Rust engine later
- Reduces the risk of platform sprawl

### Negative

- Some future integrations may require new adapter layers
- The engine boundary must be kept disciplined from the start
