"""Network Gap Agent — analyzes coverage and identifies missing perspectives.

Analyzes the accepted-attendee graph against community target shares and the
viewpoint-balance principle; surfaces missing voices, missing organizations,
over-represented groups, and recommended invitees.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class NetworkGapAgent(Agent):
    name = "network_gap"
    role = "Network Gap Agent"
    instruction = ("Analyze attendee coverage vs community targets and the viewpoint-balance "
                   "principle; surface missing voices, over-represented groups, and recommended invitees.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        # Accepted attendees = people whose invitation is accepted (+ confirmed speakers).
        accepted_people = set()
        for inv in ctx["invitations"]:
            if inv["status"] == "accepted":
                for e in ctx["edges"]:
                    if e["src"] == inv["id"] and e["rel"] == "sent_to":
                        accepted_people.add(e["dst"])
        for sp in cb.speakers_for(ctx, "event:curve-2027"):
            if sp["status"] == "confirmed":
                accepted_people.add(sp["person"])

        communities = {c["id"]: c for c in ctx["communities"]}
        counts: dict[str, int] = {cid: 0 for cid in communities}
        for pid in accepted_people:
            comm = cb.community_of_person(ctx, pid)
            if comm in counts:
                counts[comm] += 1
        total = sum(counts.values()) or 1

        under, over, missing_comms = [], [], []
        max_share, max_comm = 0.0, None
        for cid, c in communities.items():
            share = counts[cid] / total
            if share > max_share:
                max_share, max_comm = share, cid
            target = c["data"].get("target_share", 0)
            if counts[cid] == 0:
                missing_comms.append(cid)
            elif share < target - 0.05:
                under.append((cid, share, target))
            if share > 0.35:
                over.append((cid, share))

        # Missing organizations / labs: zero accepted attendees.
        org_has = set()
        for pid in accepted_people:
            o = cb.org_of(ctx, pid)
            if o:
                org_has.add(o)
        missing_orgs = [o for o in ctx["ai_labs"] + ctx["organizations"]
                        if o["id"] not in org_has and o["data"].get("kind") in ("frontier_lab", "civil_society")]

        # Recommended invitees: high-influence people in missing communities, not yet accepted.
        recommended = []
        for p in ctx["people"]:
            if p["id"] in accepted_people or p["data"].get("team"):
                continue
            comm = cb.community_of_person(ctx, p["id"])
            if comm in missing_comms and p["data"].get("influence", 0) >= 0.6:
                recommended.append({"person": p["id"], "fills": comm, "why": p["data"].get("note", "fills a missing community")})

        comm_titles = {cid: c["title"] for cid, c in communities.items()}
        bullets: list[str] = []
        for cid in missing_comms:
            bullets.append(f"MISSING VOICE: no confirmed attendee from {comm_titles[cid]}.")
        for o in missing_orgs:
            bullets.append(f"MISSING ORG: {o['title']} ({o['data'].get('note','no confirmed attendee')}).")
        for cid, share in over:
            bullets.append(f"OVER-REPRESENTED: {comm_titles[cid]} at {share:.0%} (>35% balance limit).")
        for cid, share, target in under:
            bullets.append(f"UNDER target: {comm_titles[cid]} {share:.0%} vs {target:.0%} goal.")

        headline = (f"Network gaps: {len(missing_comms)} missing community voice(s), {len(missing_orgs)} missing org(s); "
                    f"largest bloc is {comm_titles.get(max_comm,'—')} at {max_share:.0%}.")
        return {
            "headline": headline, "bullets": bullets,
            "missing_communities": missing_comms,
            "missing_orgs": [o["id"] for o in missing_orgs],
            "over_represented": [c for c, _ in over],
            "max_share": round(max_share, 2), "max_community": max_comm,
            "recommended_invitees": recommended,
            "community_counts": counts,
        }
