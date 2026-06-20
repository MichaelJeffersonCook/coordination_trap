"""Event Matching Agent — recommends attendees for an event.

Scores candidates on seniority, expertise, organization, geography, previous
attendance, existing relationships, and diversity objectives.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


SENIORITY = {"principal": 1.0, "senior": 0.7, "mid": 0.4}


class EventMatchingAgent(Agent):
    name = "event_matching"
    role = "Event Matching Agent"
    instruction = ("Recommend and rank attendees for the event on seniority, expertise, "
                   "previous attendance, relationships and diversity objectives.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        domain = domain or {}
        # Who's already accepted (don't re-recommend).
        accepted = set()
        for inv in ctx["invitations"]:
            if inv["status"] == "accepted":
                for e in ctx["edges"]:
                    if e["src"] == inv["id"] and e["rel"] == "sent_to":
                        accepted.add(e["dst"])

        missing_comms = set(domain.get("network_gap", {}).get("findings", {}).get("missing_communities", []))
        attended_before = {e["dst"] for e in ctx["edges"] if e["rel"] == "attends"}
        knows_team = {e["dst"] for e in ctx["edges"] if e["rel"] == "knows" and ctx_team(ctx, e["src"])} | \
                     {e["src"] for e in ctx["edges"] if e["rel"] == "knows" and ctx_team(ctx, e["dst"])}

        ranked = []
        for p in ctx["people"]:
            if p["data"].get("team") or p["id"] in accepted:
                continue
            d = p["data"]
            score = 0.45 * SENIORITY.get(d.get("seniority"), 0.4) + 0.35 * d.get("influence", 0.5)
            reasons = [f"{d.get('seniority','mid')} / influence {d.get('influence',0.5):.2f}"]
            if p["id"] in attended_before:
                score += 0.1; reasons.append("attended a prior Curve")
            if p["id"] in knows_team:
                score += 0.05; reasons.append("warm relationship with the team")
            comm = cb.community_of_person(ctx, p["id"])
            if comm in missing_comms:
                score += 0.2; reasons.append("fills a missing community voice")
            if d.get("international"):
                score += 0.05; reasons.append("international")
            ranked.append({"person": p["id"], "title": p["title"], "score": round(min(score, 1.0), 2),
                           "reasons": reasons, "community": comm})

        ranked.sort(key=lambda r: r["score"], reverse=True)
        top = ranked[:6]
        people = {p["id"]: p["title"] for p in ctx["people"]}
        bullets = [f"{people.get(r['person'], r['person'])} — {r['score']} ({'; '.join(r['reasons'])})" for r in top]
        headline = (f"Event matching: {len(ranked)} candidate(s) scored; top {len(top)} recommended to close the "
                    "attendee mix for The Curve 2027.")
        return {"headline": headline, "bullets": bullets, "ranked": ranked,
                "recommended_invitations": [r["person"] for r in top]}


def ctx_team(ctx: dict[str, Any], pid: str) -> bool:
    for p in ctx["people"]:
        if p["id"] == pid:
            return bool(p["data"].get("team"))
    return False
