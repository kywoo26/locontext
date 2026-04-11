PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    source_kind TEXT NOT NULL,
    requested_locator TEXT NOT NULL,
    resolved_locator TEXT,
    canonical_locator TEXT NOT NULL,
    docset_root TEXT NOT NULL,
    active_snapshot_id TEXT,
    created_at TEXT,
    updated_at TEXT,
    UNIQUE (canonical_locator)
);

CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    status TEXT NOT NULL,
    fetched_at TEXT,
    content_hash TEXT,
    etag TEXT,
    last_modified TEXT,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_snapshots_one_active_per_source
ON snapshots(source_id)
WHERE is_active = 1;

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    requested_locator TEXT NOT NULL,
    resolved_locator TEXT NOT NULL,
    canonical_locator TEXT NOT NULL,
    title TEXT,
    section_path TEXT,
    content_hash TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    UNIQUE (snapshot_id, canonical_locator)
);

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_snapshot_id ON documents(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_documents_canonical_locator ON documents(canonical_locator);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE,
    FOREIGN KEY (snapshot_id) REFERENCES snapshots(snapshot_id) ON DELETE CASCADE,
    FOREIGN KEY (document_id) REFERENCES documents(document_id) ON DELETE CASCADE,
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_source_id ON chunks(source_id);
CREATE INDEX IF NOT EXISTS idx_chunks_snapshot_id ON chunks(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunk_fts USING fts5(
    chunk_id UNINDEXED,
    text,
    content='chunks',
    content_rowid='rowid'
);
