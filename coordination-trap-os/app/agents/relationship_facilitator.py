"""Relationship Facilitator Agent — recommends valuable introductions.

Analyzes attendee backgrounds and the relationship graph to suggest strategic,
cross-community introductions that don't already exist.
"""
from __future__ import annotations

from itertools import combinations
from typing import Any

from .base import Agent
from .. import context_builder as cb


class RelationshipFacilitatorAgent(Agent):
    name = "relationship_facilitator"
    role = "Relationship Facilitator Agent"
    instruction = ("Recommend high-value cross-community introductions between attendees who "
                   "don't already know each other.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        # Attendees = accepted invitations + confirmed speakers.
        attendees = set()
        for inv in ctx["invitations"]:
            if inv["status"] == "accepted":
                attendees |= {e["dst"] for e in ctx["edges"] if e["src"] == inv["id"] and e["rel"] == "sent_to"}
        for sp in cb.speakers_for(ctx, "event:curve-2027"):
            if sp["status"] == "confirmed":
                attendees.add(sp["person"])

        # Existing "knows" pairs (undirected).
        known = set()
        for e in ctx["edges"]:
            if e["rel"] in ("knows", "introduced_to"):
                known.add(frozenset((e["src"], e["dst"])))

        people = cb.person_lookup(ctx)
        intros = []
        for a, b in combinations(sorted(attendees), 2):
            if frozenset((a, b)) in known:
                continue
            ca, cb_ = cb.community_of_person(ctx, a), cb.community_of_person(ctx, b)
            if not ca or not cb_ or ca == cb_:
                continue  # only suggest cross-community bridges
            pa, pb = people.get(a, {}).get("data", {}), people.get(b, {}).get("data", {})
            # Value: pair senior people, especially across a viewpoint divide.
            value = pa.get("influence", 0) + pb.get("influence", 0)
            viewpoint_bridge = bool(pa.get("viewpoint") and pb.get("viewpoint") and pa.get("viewpoint") != pb.get("viewpoint"))
            if viewpoint_bridge:
                value += 0.5
            intros.append({
                "a": a, "b": b, "value": round(value, 2),
                "reason": _reason(people.get(a, {}), people.get(b, {}), viewpoint_bridge),
            })

        intros.sort(key=lambda x: x["value"], reverse=True)
        top = intros[:5]
        bullets = [f"{people.get(i['a'],{}).get('title',i['a'])} ↔ {people.get(i['b'],{}).get('title',i['b'])} — {i['reason']}"
                   for i in top]
        headline = f"Relationship facilitator: {len(top)} high-value introduction(s) recommended across communities."
        return {"headline": headline, "bullets": bullets, "introductions": top}


def _reason(a: dict[str, Any], b: dict[str, Any], bridge: bool) -> str:
    da, db = a.get("data", {}), b.get("data", {})
    if bridge:
        return f"viewpoint bridge ({da.get('viewpoint')} ↔ {db.get('viewpoint')})"
    return f"connect {da.get('role','')} and {db.get('role','')} across communities"
