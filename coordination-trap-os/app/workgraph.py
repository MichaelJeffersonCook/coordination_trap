"""Query + mutation helpers over the Work Graph (nodes + edges)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import db


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------
def upsert_node(node_id: str, type: str, title: str, status: str | None,
                data: dict[str, Any] | None = None, actor: str = "system") -> None:
    now = _now()
    new_data = json.dumps(data or {})
    with db.session() as conn:
        existing = conn.execute(
            "SELECT title, status, data FROM nodes WHERE id = ?", (node_id,)
        ).fetchone()
        # Snapshot the PRIOR state into history when content actually changes.
        if existing and (existing["title"] != title
                         or existing["status"] != status
                         or existing["data"] != new_data):
            last = conn.execute(
                "SELECT COALESCE(MAX(version), 0) AS v FROM node_versions WHERE node_id = ?",
                (node_id,),
            ).fetchone()["v"]
            conn.execute(
                "INSERT INTO node_versions (node_id, version, title, status, data, actor, ts) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (node_id, last + 1, existing["title"], existing["status"],
                 existing["data"], actor, now),
            )
        conn.execute(
            """INSERT INTO nodes (id, type, title, status, data, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 type=excluded.type, title=excluded.title, status=excluded.status,
                 data=excluded.data, updated_at=excluded.updated_at""",
            (node_id, type, title, status, new_data, now, now),
        )


def add_edge(src: str, rel: str, dst: str, data: dict[str, Any] | None = None) -> None:
    edge_id = f"{src}|{rel}|{dst}"
    with db.session() as conn:
        conn.execute(
            """INSERT INTO edges (id, src, rel, dst, data) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET data=excluded.data""",
            (edge_id, src, rel, dst, json.dumps(data or {})),
        )


def log_event(actor: str, kind: str, summary: str,
              node_id: str | None = None, data: dict[str, Any] | None = None) -> None:
    with db.session() as conn:
        conn.execute(
            "INSERT INTO events (ts, actor, kind, node_id, summary, data) VALUES (?, ?, ?, ?, ?, ?)",
            (_now(), actor, kind, node_id, summary, json.dumps(data or {})),
        )


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------
def nodes_by_type(type: str) -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute(
            "SELECT * FROM nodes WHERE type = ? ORDER BY id", (type,)
        ).fetchall()
    return [db.row_to_node(r) for r in rows]


def get_node(node_id: str) -> dict[str, Any] | None:
    with db.session() as conn:
        row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
    return db.row_to_node(row) if row else None


def all_nodes() -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM nodes ORDER BY type, id").fetchall()
    return [db.row_to_node(r) for r in rows]


def all_edges() -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM edges").fetchall()
    return [
        {"src": r["src"], "rel": r["rel"], "dst": r["dst"], "data": json.loads(r["data"])}
        for r in rows
    ]


def neighbors(node_id: str, rel: str | None = None, direction: str = "out") -> list[dict[str, Any]]:
    """Return nodes connected to node_id. direction: out|in|both."""
    edges = all_edges()
    ids: set[str] = set()
    for e in edges:
        if rel and e["rel"] != rel:
            continue
        if direction in ("out", "both") and e["src"] == node_id:
            ids.add(e["dst"])
        if direction in ("in", "both") and e["dst"] == node_id:
            ids.add(e["src"])
    return [n for n in all_nodes() if n["id"] in ids]


def edges_by_rel(rel: str) -> list[dict[str, Any]]:
    return [e for e in all_edges() if e["rel"] == rel]


def recent_events(limit: int = 50, kind: str | None = None) -> list[dict[str, Any]]:
    with db.session() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM events WHERE kind = ? ORDER BY id DESC LIMIT ?", (kind, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [
        {
            "id": r["id"], "ts": r["ts"], "actor": r["actor"], "kind": r["kind"],
            "node_id": r["node_id"], "summary": r["summary"], "data": json.loads(r["data"]),
        }
        for r in rows
    ]


def goal_tree() -> list[dict[str, Any]]:
    """Goals nested by the `cascades_to` relation, company → department → role."""
    goals = {g["id"]: g for g in nodes_by_type("goal")}
    children: dict[str, list[str]] = {}
    has_parent: set[str] = set()
    for e in edges_by_rel("cascades_to"):
        children.setdefault(e["src"], []).append(e["dst"])
        has_parent.add(e["dst"])
    owners = {e["src"]: e["dst"] for e in edges_by_rel("owned_by")}

    def build(gid: str) -> dict[str, Any]:
        g = dict(goals[gid])
        g["owner"] = owners.get(gid)
        g["children"] = [build(c) for c in children.get(gid, []) if c in goals]
        return g

    roots = [gid for gid in goals if gid not in has_parent]
    return [build(r) for r in sorted(roots)]


def goals_for_node(node_id: str) -> list[str]:
    """Walk a feature/initiative/task UP to every goal it ladders into.

    feature -belongs_to-> initiative -part_of-> goal(dept) <-cascades_to- goal(company)
    """
    edges = all_edges()
    up_rels = {"belongs_to", "part_of"}
    reached_goals: set[str] = set()
    frontier = {node_id}
    seen: set[str] = set()
    goal_ids = {g["id"] for g in nodes_by_type("goal")}
    while frontier:
        cur = frontier.pop()
        if cur in seen:
            continue
        seen.add(cur)
        if cur in goal_ids:
            reached_goals.add(cur)
            # climb the cascade upward (child is the dst of cascades_to)
            for e in edges:
                if e["rel"] == "cascades_to" and e["dst"] == cur:
                    frontier.add(e["src"])
            continue
        for e in edges:
            if e["src"] == cur and e["rel"] in up_rels:
                frontier.add(e["dst"])
    return sorted(reached_goals)


def node_history(node_id: str) -> list[dict[str, Any]]:
    """Prior versions of a node, newest first."""
    with db.session() as conn:
        rows = conn.execute(
            "SELECT * FROM node_versions WHERE node_id = ? ORDER BY version DESC", (node_id,)
        ).fetchall()
    return [
        {"version": r["version"], "title": r["title"], "status": r["status"],
         "data": json.loads(r["data"]), "actor": r["actor"], "ts": r["ts"]}
        for r in rows
    ]


def graph_summary() -> dict[str, int]:
    counts: dict[str, int] = {}
    for n in all_nodes():
        counts[n["type"]] = counts.get(n["type"], 0) + 1
    return counts
