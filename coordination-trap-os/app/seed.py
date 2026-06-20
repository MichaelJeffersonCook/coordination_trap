"""Load mock systems-of-record data (data/seed/*.json) into the Work Graph.

Each seed file represents one or more systems of record. Nodes carry inline
`edges` which are materialized after all nodes exist. Risks and decisions are
deliberately NOT seeded — agents generate those at brief time, demonstrating
the push model.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import config, db, workgraph as wg

# Files loaded as node/edge sources.
NODE_FILES = ["context.json", "goals.json", "roles.json", "communities.json", "people.json", "events.json", "ecosystem.json"]
# Files loaded as event sources.
EVENT_FILES = ["changes.json"]


def _reset() -> None:
    with db.session() as conn:
        for table in ("edges", "nodes", "node_versions", "events", "approvals", "briefings"):
            conn.execute(f"DELETE FROM {table}")


def load(reset: bool = True) -> dict[str, int]:
    db.init_db()
    if reset:
        _reset()

    pending_edges: list[tuple[str, str, str, dict]] = []

    for fname in NODE_FILES:
        path = config.SEED_DIR / fname
        doc = json.loads(path.read_text())
        for node in doc.get("nodes", []):
            wg.upsert_node(node["id"], node["type"], node["title"],
                           node.get("status"), node.get("data", {}))
            for edge in node.get("edges", []):
                pending_edges.append((node["id"], edge["rel"], edge["dst"], edge.get("data", {})))

    for src, rel, dst, data in pending_edges:
        wg.add_edge(src, rel, dst, data)

    # Events get yesterday's timestamp so "what changed since yesterday" works.
    yesterday = (_demo_now() - timedelta(hours=12)).isoformat()
    for fname in EVENT_FILES:
        doc = json.loads((config.SEED_DIR / fname).read_text())
        with db.session() as conn:
            for ev in doc.get("events", []):
                conn.execute(
                    "INSERT INTO events (ts, actor, kind, node_id, summary, data) VALUES (?, ?, ?, ?, ?, ?)",
                    (yesterday, ev["actor"], ev["kind"], ev.get("node_id"),
                     ev["summary"], json.dumps(ev.get("data", {}))),
                )

    return wg.graph_summary()


def _demo_now() -> datetime:
    try:
        d = datetime.fromisoformat(config.DEMO_TODAY)
        return d.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


if __name__ == "__main__":
    summary = load()
    print("Seeded Work Graph:", summary)
