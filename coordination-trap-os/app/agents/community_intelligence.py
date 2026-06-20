"""Community Intelligence Agent — understands the AI ecosystem.

Tracks communities/organizations/influence networks, identifies emerging
leaders, and detects ecosystem shifts.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class CommunityIntelligenceAgent(Agent):
    name = "community_intelligence"
    role = "Community Intelligence Agent"
    instruction = ("Track the AI ecosystem: communities, organizations, influence networks; "
                   "identify emerging leaders and detect ecosystem shifts.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        people = ctx["people"]
        emerging = [p for p in people if p["data"].get("emerging")]

        # Community map: people per community (via org → community).
        counts: dict[str, int] = {}
        for p in people:
            if p["data"].get("team"):
                continue
            comm = cb.community_of_person(ctx, p["id"])
            if comm:
                counts[comm] = counts.get(comm, 0) + 1

        # Ecosystem shifts: hot publications + policy movement.
        shifts = [pub["title"] for pub in ctx["publications"] if pub["data"].get("heat") == "high"]
        shifts += [pol["title"] for pol in ctx["policy_initiatives"] if pol["data"].get("heat") == "rising"]

        comm_titles = {c["id"]: c["title"] for c in ctx["communities"]}
        bullets: list[str] = []
        for p in emerging:
            bullets.append(f"EMERGING LEADER: {p['title']} — {p['data'].get('note','rising influence')}.")
        for s in shifts:
            bullets.append(f"ECOSYSTEM SHIFT: {s}.")
        bullets.append("Community map: " + ", ".join(f"{comm_titles.get(k,k)} {v}" for k, v in sorted(counts.items())))

        headline = (f"Community intelligence: {len(emerging)} emerging leader(s) and "
                    f"{len(shifts)} ecosystem shift(s) worth surfacing to the program team.")
        return {
            "headline": headline, "bullets": bullets,
            "emerging_leaders": [p["id"] for p in emerging],
            "community_counts": counts,
            "ecosystem_shifts": shifts,
        }
