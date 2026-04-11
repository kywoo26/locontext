# ADR 0003 - V1 Retrieval and Store Direction

## Status

Proposed

## Decision

Use a lexical-first retrieval implementation for v1 and use SQLite as the project-local system of record.

The architecture should remain hybrid-ready, but hybrid retrieval is not part of the v1 implementation.

## Drivers

- Lower initial complexity
- Easier debugging of ingest, chunking, and refresh behavior
- Inspectable local state for a solo maintainer
- Lower runtime and dependency risk
- Strong fit for project-local operation
- Cleaner future engine replacement boundary

## Chosen direction

### Retrieval

- lexical-first search in v1
- structure-aware chunking
- provenance-aware ranking inputs
- explicit support for future hybrid expansion behind the engine boundary

### Store

SQLite is the v1 system of record for:

- source registry
- snapshot state
- document metadata
- chunk metadata
- lexical query tables

## Deferred work

The following are deferred beyond v1:

- embeddings-first retrieval
- vector database requirements
- dense+sparse hybrid retrieval
- reranking pipelines
- daemonized background indexing

## Why not hybrid from day 1

Hybrid retrieval would increase:

- dependency complexity
- runtime compatibility risk
- schema complexity
- refresh recomputation complexity
- debugging difficulty during the first end-to-end build

That tradeoff is not justified before source identity, canonicalization, chunking, and refresh semantics are stable.

## Consequences

### Positive

- Faster path to a stable refreshable local engine
- Easier diagnosis of retrieval failures
- Simpler packaging and project-local operation
- Better control over lifecycle correctness

### Negative

- Semantic recall may remain limited in v1
- Some retrieval gaps may remain until hybrid work is added later
