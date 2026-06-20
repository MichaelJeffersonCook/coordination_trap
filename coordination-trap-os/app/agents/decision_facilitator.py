"""Decision Facilitator Agent — turns decision-risk into human-ready briefs.

Output is a decision brief: issue, context, options with tradeoffs, a
recommendation, the required decision owner, and a deadline — the artifact
pushed to a human for approval.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class DecisionFacilitatorAgent(Agent):
    name = "decision_facilitator"
    role = "Decision Facilitator Agent"
    instruction = ("Prepare decision briefs: issue, context, options, tradeoffs, "
                   "recommendation, decision owner, and deadline.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        domain = domain or {}
        risks = domain.get("risk_watcher", {}).get("findings", {}).get("risks", [])
        briefs: list[dict[str, Any]] = []

        types = {r["risk_type"] for r in risks}
        if "decision" in types:
            briefs.append(self._keynote_brief(ctx, domain))
        if "perspective" in types:
            briefs.append(self._balance_brief(ctx, domain))

        bullets = [f"DECISION NEEDED: {b['issue']} — owner {b['owner_role']}, due {b['deadline']}" for b in briefs]
        headline = f"Decision Facilitator: {len(briefs)} decision brief(s) prepared for human sign-off."
        return {"headline": headline, "bullets": bullets, "briefs": briefs}

    def _keynote_brief(self, ctx: dict[str, Any], domain: dict[str, Any]) -> dict[str, Any]:
        people = cb.person_lookup(ctx)
        ops = domain.get("event_operations", {}).get("findings", {})
        return {
            "id": "decision:keynote",
            "issue": "Keynote speaker for The Curve 2027 is not yet selected.",
            "context": [
                f"{ops.get('confirmed_speakers', 0)} of {ops.get('target_speakers', 6)} speakers confirmed; "
                f"{ops.get('rsvp_days')} days to the RSVP deadline.",
                "Dario (Anthropic) is confirmed and marked a keynote candidate.",
                "Fei (Stanford HAI) and Demis (Google DeepMind) were invited as speakers but have not responded.",
                "Positioning depends on frontier-lab principals visibly anchoring the program.",
            ],
            "options": [
                {"option": "A. Lock Dario as keynote now",
                 "tradeoffs": "Removes program risk immediately; anchors with a confirmed frontier-lab principal. Slightly less 'neutral ground' optics than a policy/academic keynote."},
                {"option": "B. Hold one week for Fei or Demis, then default to Dario",
                 "tradeoffs": "Preserves a marquee alternative; risks leaving the keynote unannounced too close to the deadline."},
                {"option": "C. Co-keynote: a frontier-lab principal + a policy/civil-society voice",
                 "tradeoffs": "Strongest viewpoint-balance signal; depends on confirming a second principal-level voice fast."},
            ],
            "recommendation": ("Option A + C: lock Dario now to remove program risk, and pursue a policy/"
                               "civil-society co-keynote to honor the viewpoint-balance principle."),
            "owner_role": "President", "supporting_roles": ["CEO", "COO"],
            "deadline": "2027-04-28", "affects": "event:curve-2027", "requires_approval": True,
            "strategic_alignment": {
                "advances_goals": ["Build stronger connections across frontier AI labs",
                                   "Make The Curve 2027 the definitive frontier-governance convening"],
                "governing_principle": "Every governance convening must hold genuine viewpoint balance.",
                "note": "A co-keynote satisfies both the frontier-connections goal and the balance principle.",
            },
        }

    def _balance_brief(self, ctx: dict[str, Any], domain: dict[str, Any]) -> dict[str, Any]:
        gap = domain.get("network_gap", {}).get("findings", {})
        missing = [self._title(ctx, c) for c in gap.get("missing_communities", [])]
        recs = gap.get("recommended_invitees", [])
        people = cb.person_lookup(ctx)
        rec_names = ", ".join(people.get(r["person"], {}).get("title", r["person"]) for r in recs) or "candidates on file"
        return {
            "id": "decision:balance",
            "issue": "The attendee mix violates the viewpoint-balance principle (missing voices + an over-represented bloc).",
            "context": [
                f"Missing community voices: {', '.join(missing) or 'none'}.",
                f"Largest bloc is at {gap.get('max_share', 0):.0%} (35% balance limit).",
                "Open-weights and civil-society perspectives are absent from the confirmed list.",
                f"Network Gap recommends inviting: {rec_names}.",
            ],
            "options": [
                {"option": "A. Issue targeted invites to the recommended missing voices",
                 "tradeoffs": "Restores balance; requires relationship owners + fast turnaround inside the VIP sign-off rule."},
                {"option": "B. Accept the imbalance for this convening",
                 "tradeoffs": "Lower effort; directly contradicts the balance principle and the viewpoint-diversity goal."},
                {"option": "C. Rebalance by capping the over-represented bloc and back-filling",
                 "tradeoffs": "Strong balance outcome; politically sensitive with already-accepted guests."},
            ],
            "recommendation": "Option A: approve targeted invitations to the recommended civil-society and open-weights voices under the VIP sign-off rule.",
            "owner_role": "President", "supporting_roles": ["CEO", "COO"],
            "deadline": "2027-04-27", "affects": "goal:company-viewpoint-diversity", "requires_approval": True,
            "strategic_alignment": {
                "advances_goals": ["Improve diversity of viewpoints across convenings"],
                "governing_principle": "Every governance convening must hold genuine viewpoint balance.",
                "note": "Directly serves the viewpoint-diversity company goal.",
            },
        }

    def _title(self, ctx: dict[str, Any], cid: str) -> str:
        n = next((c for c in ctx["communities"] if c["id"] == cid), None)
        return n["title"] if n else cid
