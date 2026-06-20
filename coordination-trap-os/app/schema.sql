-- The Coordination Trap :: AI-Native Product OS
-- Work Graph schema.
--
-- The Work Graph is modeled as a generic property graph: every entity is a
-- `node` with a type and a JSON blob of attributes; every relationship is an
-- `edge` with a relation type. This keeps all 16 entity types in two tables,
-- which makes graph traversal and the graph viewer trivial, while still
-- letting agents query by type + status.

CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,            -- e.g. "feature:one-click-checkout"
    type        TEXT NOT NULL,               -- goal|initiative|project|feature|task|risk|...
    title       TEXT NOT NULL,
    status      TEXT,                        -- free-form per type (e.g. on_track, blocked, open)
    data        TEXT NOT NULL DEFAULT '{}',  -- JSON attributes specific to the node type
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS edges (
    id      TEXT PRIMARY KEY,                -- "src|rel|dst"
    src     TEXT NOT NULL REFERENCES nodes(id),
    rel     TEXT NOT NULL,                   -- belongs_to|owns|affects|blocks|resolves|relates_to|records|part_of
    dst     TEXT NOT NULL REFERENCES nodes(id),
    data    TEXT NOT NULL DEFAULT '{}'
);

-- Version history for nodes. Whenever a node's title/status/data changes, the
-- PRIOR state is snapshotted here first. This is the OS's memory: context,
-- goals and decisions evolve over time and the trail is preserved.
CREATE TABLE IF NOT EXISTS node_versions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id     TEXT NOT NULL,
    version     INTEGER NOT NULL,            -- 1-based; the snapshot's own number
    title       TEXT,
    status      TEXT,
    data        TEXT NOT NULL DEFAULT '{}',
    actor       TEXT NOT NULL DEFAULT 'system',
    ts          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_node_versions_node ON node_versions(node_id);

-- Append-only log of what agents observed / produced. This is how the
-- Documentation Steward writes outputs back into the graph and how the brief
-- answers "what changed since yesterday".
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    actor       TEXT NOT NULL,               -- agent name or "human:<id>" or "system"
    kind        TEXT NOT NULL,               -- observation|analysis|decision_brief|approval|log
    node_id     TEXT,                        -- optional related node
    summary     TEXT NOT NULL,
    data        TEXT NOT NULL DEFAULT '{}'
);

-- Human approval flow. Agents create approval requests; humans resolve them.
CREATE TABLE IF NOT EXISTS approvals (
    id           TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    requested_by TEXT NOT NULL,              -- agent that raised it
    owner_role   TEXT NOT NULL,              -- who must decide (e.g. "Product Manager")
    title        TEXT NOT NULL,
    detail       TEXT NOT NULL,
    related_node TEXT,                        -- e.g. a decision or risk node
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
    resolved_at  TEXT,
    resolved_by  TEXT,
    note         TEXT
);

-- Persisted daily briefings so the dashboard and n8n can fetch the latest.
CREATE TABLE IF NOT EXISTS briefings (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    for_date    TEXT NOT NULL,
    payload     TEXT NOT NULL                 -- full JSON brief
);

CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src);
CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
