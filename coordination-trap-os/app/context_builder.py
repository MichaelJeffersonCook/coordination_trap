"""Layer-2 Context Builder for the Relationship & Events OS.

Assembles a single context package from the Work Graph that every agent reasons
over. In production this is where n8n-fetched data from Attio / Google Sheets /
news feeds would be normalized; here it reads the seeded Work Graph.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import config, workgraph as wg


def _demo_now() -> datetime:
    try:
        return datetime.fromisoformat(config.DEMO_TODAY).replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def build() -> dict[str, Any]:
    """Return the context package: graph slices keyed by entity type."""
    edges = wg.all_edges()
    return {
        "as_of": config.DEMO_TODAY,
        "now": _demo_now(),
        # Goals + cascade
        "goals": wg.nodes_by_type("goal"),
        "goal_tree": wg.goal_tree(),
        # Organizational context (Memory + Rules)
        "org_profile": wg.nodes_by_type("org_profile"),
        "positioning": wg.nodes_by_type("positioning"),
        "principles": wg.nodes_by_type("principle"),
        "rules": wg.nodes_by_type("rule"),
        # The network
        "people": wg.nodes_by_type("person"),
        "organizations": wg.nodes_by_type("organization"),
        "communities": wg.nodes_by_type("community"),
        "ai_labs": wg.nodes_by_type("ai_lab"),
        # Events + program
        "events": wg.nodes_by_type("event"),
        "themes": wg.nodes_by_type("theme"),
        "topics": wg.nodes_by_type("topic"),
        # Pipeline
        "invitations": wg.nodes_by_type("invitation"),
        "rsvps": wg.nodes_by_type("rsvp"),
        "attendance": wg.nodes_by_type("attendance"),
        "follow_ups": wg.nodes_by_type("follow_up"),
        "introductions": wg.nodes_by_type("introduction"),
        # Ecosystem signals
        "publications": wg.nodes_by_type("publication"),
        "policy_initiatives": wg.nodes_by_type("policy_initiative"),
        "edges": edges,
        "recent_changes": wg.recent_events(limit=25, kind="observation"),
    }


# ---------------------------------------------------------------------------
# Helpers shared by agents
# ---------------------------------------------------------------------------
def goals_lookup(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {g["id"]: g for g in ctx["goals"]}


def aligned_goals(node_id: str) -> list[str]:
    return wg.goals_for_node(node_id)


def person_lookup(ctx: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {p["id"]: p for p in ctx["people"]}


def org_of(ctx: dict[str, Any], person_id: str) -> str | None:
    for e in ctx["edges"]:
        if e["src"] == person_id and e["rel"] == "belongs_to":
            return e["dst"]
    return None


def community_of_org(ctx: dict[str, Any], org_id: str | None) -> str | None:
    if not org_id:
        return None
    for e in ctx["edges"]:
        if e["src"] == org_id and e["rel"] == "part_of":
            return e["dst"]
    return None


def community_of_person(ctx: dict[str, Any], person_id: str) -> str | None:
    return community_of_org(ctx, org_of(ctx, person_id))


def curve_event(ctx: dict[str, Any]) -> dict[str, Any] | None:
    return next((e for e in ctx["events"] if e["id"] == "event:curve-2027"), None)


def speakers_for(ctx: dict[str, Any], event_id: str) -> list[dict[str, Any]]:
    """Return [{person_id, status}] for an event's `includes` edges."""
    out = []
    for e in ctx["edges"]:
        if e["src"] == event_id and e["rel"] == "includes":
            out.append({"person": e["dst"], "status": e.get("data", {}).get("speaker_status", "invited")})
    return out


def days_until(date_str: str, now: datetime | None = None) -> int | None:
    now = now or _demo_now()
    try:
        target = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        return (target - now).days
    except Exception:
        return None
