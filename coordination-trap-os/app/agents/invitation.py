"""Invitation Agent — manages invitations and RSVPs.

Tracks the pipeline, monitors responses, flags RSVP risk on VIPs, and
recommends follow-ups and replacements.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class InvitationAgent(Agent):
    name = "invitation"
    role = "Invitation Agent"
    instruction = ("Track invitations and RSVPs; monitor responses, flag RSVP risk, and "
                   "recommend follow-ups and replacements.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        event = cb.curve_event(ctx)
        people = cb.person_lookup(ctx)
        d = event["data"] if event else {}
        target = d.get("target_attendance", 250)
        accepted = d.get("accepted", 0)
        invited = d.get("invited", 0)
        no_response = d.get("no_response", 0)
        declined = d.get("declined", 0)

        # VIP RSVP risk: VIP invitations with no response and aging.
        rsvp_risks, follow_ups = [], []
        for inv in ctx["invitations"]:
            if inv["status"] in ("no_response", "sent") and inv["data"].get("vip"):
                pid = next((e["dst"] for e in ctx["edges"] if e["src"] == inv["id"] and e["rel"] == "sent_to"), None)
                days = inv["data"].get("days_since_sent", 0)
                rsvp_risks.append({"invitation": inv["id"], "person": pid, "days": days,
                                   "owner": inv["data"].get("owner")})
                follow_ups.append({"person": pid, "owner": inv["data"].get("owner"),
                                   "action": f"Personal follow-up — unanswered {days}d (VIP)"})

        gap = max(0, target - accepted)
        bullets = [f"Pipeline: {invited} invited · {accepted} accepted · {declined} declined · {no_response} no-response."]
        bullets.append(f"Confirmed {accepted}/{target} ({accepted/target:.0%}); {gap} short of target.")
        for r in rsvp_risks:
            bullets.append(f"RSVP RISK: {people.get(r['person'],{}).get('title', r['person'])} — unanswered {r['days']}d "
                           f"(owner: {people.get(r['owner'],{}).get('title','—')}).")

        headline = (f"Invitations: {accepted}/{target} confirmed ({gap} to go); "
                    f"{len(rsvp_risks)} VIP RSVP(s) at risk and need a personal follow-up.")
        return {
            "headline": headline, "bullets": bullets,
            "pipeline": {"invited": invited, "accepted": accepted, "declined": declined, "no_response": no_response},
            "confirmed": accepted, "target": target, "gap_to_target": gap,
            "rsvp_risks": rsvp_risks, "follow_up_recommendations": follow_ups,
        }
