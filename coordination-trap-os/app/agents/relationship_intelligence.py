"""Relationship Intelligence Agent — continuously maintains relationship intel.

Detects job/org changes, emerging influence, and missing profile data; proposes
profile enrichments. Inputs: Attio, historical attendance, public profile data.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class RelationshipIntelligenceAgent(Agent):
    name = "relationship_intelligence"
    role = "Relationship Intelligence Agent"
    instruction = ("Maintain relationship intelligence: detect job/org changes, emerging "
                   "influence, and missing profile data; recommend profile enrichments.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        people = ctx["people"]
        # Job/org changes: surfaced in the change feed, or implied by a stale profile.
        change_ids = {e["node_id"] for e in ctx["recent_changes"] if e["data"].get("delta") == "job_change"}
        job_changes = [p for p in people if p["id"] in change_ids or "left" in p["data"].get("note", "").lower()]
        # Data-quality gaps: incomplete profiles on people who matter.
        incomplete = [p for p in people if p["data"].get("profile_complete") is False and not p["data"].get("team")]
        # Emerging influence.
        rising = [p for p in people if p["data"].get("emerging")]

        bullets: list[str] = []
        for p in job_changes:
            bullets.append(f"JOB CHANGE: {p['title']} — {p['data'].get('note','role/org changed')} (update Attio).")
        for p in incomplete:
            bullets.append(f"DATA GAP: {p['title']} profile incomplete — {p['data'].get('note','missing fields')}.")
        for p in rising:
            if p not in job_changes:
                bullets.append(f"INFLUENCE RISING: {p['title']} — {p['data'].get('note','')}".rstrip())

        headline = (f"Relationship intelligence: {len(job_changes)} job/org change(s), "
                    f"{len(incomplete)} profile gap(s), {len(rising)} rising-influence signal(s).")
        return {
            "headline": headline, "bullets": bullets,
            "job_changes": [p["id"] for p in job_changes],
            "data_quality_alerts": [p["id"] for p in incomplete],
            "influence_changes": [p["id"] for p in rising],
            "suggested_enrichments": [{"person": p["id"], "action": "Refresh org/title/contact from public sources"}
                                      for p in incomplete],
        }
