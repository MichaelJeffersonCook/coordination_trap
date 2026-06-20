"""Level 2 — Partner-agent event inbox.

Each human role has a partner agent whose job is to be that human's interface to
the organization: it turns the cross-functional pipeline's findings into a queue
of **push events**, each carrying agent-recommended responses. The human can
**ignore**, **accept a recommendation**, or **write their own response** — and
those responses persist in the Work Graph (and survive regeneration).
"""
from __future__ import annotations

from typing import Any

from . import briefing, db
from . import workgraph as wg

ACTED = {"ignored", "accepted", "responded"}

# Which role owns which kind of surfaced item.
ROLE_BY_RISK_TYPE = {
    "attendance": "role:coo", "program": "role:president", "perspective": "role:president",
    "relationship": "role:coo", "data_quality": "role:coo", "follow_up": "role:coo",
    "decision": "role:president", "strategic": "role:ceo", "governance": "role:ceo",
}
ROLE_BY_OWNER_ROLE = {"President": "role:president", "CEO": "role:ceo", "COO": "role:coo"}

# The Level-3 service agent credited with surfacing each kind of item.
SOURCE_BY_TYPE = {
    "attendance": "Status Checker", "program": "Planner", "perspective": "Network Gap",
    "relationship": "Escalation Agent", "data_quality": "Relationship Intelligence",
    "follow_up": "Documentation Agent", "decision": "Decision Agent",
    "strategic": "Planner", "governance": "Planner",
    "intro": "Meeting Agent", "emerging": "Community Intelligence",
}
RECS_BY_TYPE = {
    "attendance": ["Approve targeted invites to close the gap", "Extend the RSVP deadline a week"],
    "program": ["Lock a confirmed principal as keynote", "Hold one week for a marquee ‘yes’"],
    "perspective": ["Approve invites to the missing voices", "Cap the over-represented bloc & back-fill"],
    "relationship": ["Send a personal follow-up today", "Prepare a graceful replacement"],
    "data_quality": ["Enrich the profile from public sources", "Ask the relationship owner to confirm"],
    "follow_up": ["Complete it now", "Reassign to someone with capacity"],
    "strategic": ["Reprioritize to protect the goal", "Accept the tradeoff and note why"],
    "governance": ["Ratify the goal as-is", "Edit targets, then ratify", "Decline for now"],
    "intro": ["Schedule the intro at the event", "Make a warm email intro now"],
    "emerging": ["Add to the invite list", "Open a relationship — invite to a salon"],
}


def _push_events() -> list[dict[str, Any]]:
    return wg.nodes_by_type("push_event")


def rebuild() -> int:
    """Regenerate the inbox from the latest pipeline run. Preserves any event a
    human has already acted on; clears the rest and recreates open items."""
    ctx, domain = briefing.run_pipeline()
    name = {p["id"]: p["title"] for p in ctx["people"]}

    # Preserve acted-on events; delete the stale 'new' ones.
    acted: set[str] = set()
    with db.session() as conn:
        for n in _push_events():
            if n["data"].get("status") in ACTED:
                acted.add(n["id"])
            else:
                conn.execute("DELETE FROM edges WHERE src = ? OR dst = ?", (n["id"], n["id"]))
                conn.execute("DELETE FROM nodes WHERE id = ?", (n["id"],))

    specs: list[dict[str, Any]] = []

    # 1. Decisions → owning role, recommendations = the brief's options.
    for b in domain["decision_facilitator"]["findings"].get("briefs", []):
        specs.append(dict(
            id=f"pevt:dec:{b['id'].split(':')[-1]}", role=ROLE_BY_OWNER_ROLE.get(b["owner_role"], "role:president"),
            severity="high", kind="decision", source="Decision Agent",
            summary=b["issue"], detail=f"Recommendation: {b.get('recommendation','')}",
            recommendations=[o["option"] for o in b.get("options", [])] or RECS_BY_TYPE["decision" if False else "program"],
        ))

    # 2. Risks → role by type. (Decision-type risks are covered by the decision
    # briefs above, so skip them here to avoid a duplicate card.)
    for r in domain["risk_watcher"]["findings"].get("risks", []):
        t = r["risk_type"]
        if t == "decision":
            continue
        specs.append(dict(
            id=f"pevt:{r['id'].split(':',1)[-1]}", role=ROLE_BY_RISK_TYPE.get(t, "role:coo"),
            severity=r["severity"], kind=t, source=SOURCE_BY_TYPE.get(t, "Risk Watcher"),
            summary=r["title"], detail="", recommendations=RECS_BY_TYPE.get(t, ["Acknowledge", "Assign an owner"]),
        ))

    # 3. Recommended introductions → President (Meeting Agent).
    for i in domain["relationship_facilitator"]["findings"].get("introductions", [])[:3]:
        specs.append(dict(
            id=f"pevt:intro:{i['a'].split(':')[-1]}-{i['b'].split(':')[-1]}", role="role:president",
            severity="low", kind="intro", source="Meeting Agent",
            summary=f"Introduce {name.get(i['a'], i['a'])} ↔ {name.get(i['b'], i['b'])}",
            detail=i["reason"], recommendations=RECS_BY_TYPE["intro"],
        ))

    # 4. Emerging leaders → CEO (Community Intelligence).
    for pid in domain["community_intelligence"]["findings"].get("emerging_leaders", []):
        specs.append(dict(
            id=f"pevt:emrg:{pid.split(':')[-1]}", role="role:ceo", severity="low", kind="emerging",
            source="Community Intelligence", summary=f"Emerging leader: {name.get(pid, pid)}",
            detail=next((p["data"].get("note", "") for p in ctx["people"] if p["id"] == pid), ""),
            recommendations=RECS_BY_TYPE["emerging"],
        ))

    # 5. Open follow-ups (not overdue — those arrive as risks) → COO.
    for f in domain["post_event_knowledge"]["findings"].get("followup_opportunities", []):
        if f["status"] != "overdue":
            specs.append(dict(
                id=f"pevt:fu:{f['id'].split(':')[-1]}", role="role:coo", severity="low", kind="follow_up",
                source="Documentation Agent", summary=f["title"], detail=f"Due {f.get('due')}",
                recommendations=RECS_BY_TYPE["follow_up"],
            ))

    created = 0
    for s in specs:
        if s["id"] in acted:
            continue
        data = {
            "role": s["role"], "severity": s["severity"], "kind": s["kind"], "source_agent": s["source"],
            "detail": s["detail"], "recommendations": [{"label": r} for r in s["recommendations"]],
            "status": "new", "chosen": None, "response": None,
            "escalated": s["severity"] == "high",
        }
        wg.upsert_node(s["id"], "push_event", s["summary"], "new", data)
        wg.add_edge(s["id"], "for_role", s["role"])
        created += 1
    return created


def ensure() -> None:
    if not _push_events():
        rebuild()


def for_role(role_id: str) -> list[dict[str, Any]]:
    sev = {"high": 0, "medium": 1, "low": 2}
    items = [n for n in _push_events() if n["data"].get("role") == role_id]
    items.sort(key=lambda n: (n["data"].get("status") != "new", sev.get(n["data"].get("severity"), 3)))
    return items


def counts_by_role() -> dict[str, dict[str, int]]:
    out: dict[str, dict[str, int]] = {}
    for n in _push_events():
        r = n["data"].get("role")
        d = out.setdefault(r, {"open": 0, "total": 0})
        d["total"] += 1
        if n["data"].get("status") == "new":
            d["open"] += 1
    return out


def respond(event_id: str, action: str, rec_index: int | None = None, response: str = "") -> dict[str, Any]:
    node = wg.get_node(event_id)
    if not node or node["type"] != "push_event":
        raise KeyError(event_id)
    data = {**node["data"]}
    recs = data.get("recommendations", [])
    if action == "ignore":
        data["status"] = "ignored"
    elif action == "accept":
        data["status"] = "accepted"
        if rec_index is not None and 0 <= rec_index < len(recs):
            data["chosen"] = recs[rec_index]["label"]
    elif action == "custom":
        data["status"] = "responded"
        data["response"] = response
    else:
        raise ValueError(action)
    wg.upsert_node(event_id, "push_event", node["title"], data["status"], data,
                   actor=f"human:{data.get('role')}")
    wg.log_event(f"human:{data.get('role')}", "guidance",
                 f"{action} on '{node['title']}'" + (f" → {data.get('chosen')}" if data.get("chosen")
                 else (f" → {response}" if response else "")), node_id=event_id)
    return {"id": event_id, "status": data["status"]}
