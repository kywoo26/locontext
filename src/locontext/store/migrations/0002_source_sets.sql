PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS source_sets (
    source_set_id TEXT PRIMARY KEY,
    set_name TEXT NOT NULL,
    UNIQUE (set_name)
);

CREATE TABLE IF NOT EXISTS source_set_members (
    source_set_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    member_index INTEGER NOT NULL CHECK (member_index >= 0),
    PRIMARY KEY (source_set_id, member_index),
    UNIQUE (source_set_id, source_id),
    FOREIGN KEY (source_set_id) REFERENCES source_sets(source_set_id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(source_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_source_sets_set_name
ON source_sets(set_name, source_set_id);

CREATE INDEX IF NOT EXISTS idx_source_set_members_source_set_id
ON source_set_members(source_set_id, member_index);
