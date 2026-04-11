# ADR 0004 - Source Identity and Refresh Semantics

## Status

Proposed

## Decision

Model the docs lifecycle with separate identities for source, document, and snapshot.

Refresh is source-centric, explicit, and local-state-aware. Query reads from the latest successful local snapshot and does not silently fetch remote content.

## Drivers

- Refresh and update are core capabilities
- Hosted-provider replacement requires deterministic local state
- Canonicalization mistakes can corrupt retrieval behavior
- Query trust depends on stable source lifecycle semantics

## Identity model

### Source

A source is the logical registered input.

Examples:

- a docs root URL
- a declared web documentation target

The source remains stable over time even when fetched content changes.

### Document

A document is a canonical resource discovered within a source.

For web docs, this is typically tied to a canonical page locator.

### Snapshot

A snapshot is the fetched state of a source at a point in time.

If content changes on refresh, the source receives a new snapshot rather than becoming a new source.

## Locator handling

For web sources, locontext should track at least:

- `requested_locator`
- `resolved_locator`
- `canonical_locator`

Canonicalization should include:

- host normalization
- default-port normalization
- fragment removal
- redirect resolution
- removal of obvious tracking parameters

The requested locator must still be preserved for auditability.

## Refresh semantics

### refresh

- re-fetch a known source
- re-run canonicalization
- compare content hash and freshness metadata where available
- create a new snapshot only if content changed
- atomically promote the latest successful snapshot to active state
- reindex only affected content

### reindex

- rebuild local chunks and lexical index from the active snapshot
- perform no network fetch

### remove

- remove the source and all associated local state

## Query rule

Query operates only on the latest successful local snapshot.

Query does not silently crawl, refresh, or fetch remote sources.

## Consequences

### Positive

- Makes refresh behavior explainable and testable
- Separates identity from content versioning
- Preserves a clean local audit trail
- Supports deterministic indexing and deletion behavior

### Negative

- Requires more explicit modeling than a flat source table
- Adds lifecycle complexity earlier in the project
