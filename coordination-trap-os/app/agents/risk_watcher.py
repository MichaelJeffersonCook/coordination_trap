"""Risk Watcher Agent — synthesizes cross-functional risk for the convening.

Consumes the domain agents' findings plus the Work Graph and the Memory+Rules
layer, and emits structured risks across attendance, program, perspective,
data-quality, relationship, follow-up, decision, strategic and governance.
These are written back as `risk` nodes by the Documentation Steward.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class RiskWatcherAgent(Agent):
    name = "risk_watcher"
    role = "Risk Watcher Agent"
    instruction = ("Identify emerging cross-functional risks: attendance, program/speaker, "
                   "missing-perspective, data-quality, relationship, follow-up, decision and strategic.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        domain = domain or {}
        risks: list[dict[str, Any]] = []
        f = lambda k: domain.get(k, {}).get("findings", {})

        ops = f("event_operations")
        inv = f("invitation")
        gap = f("network_gap")
        rel = f("relationship_intelligence")

        # --- attendance risk: confirmed well below target near the deadline ---
        if "attendance_behind" in ops.get("blockers", []):
            risks.append(self._risk("risk:attendance", "attendance", "high",
                f"Attendance behind: {ops.get('confirmed')}/{ops.get('target')} confirmed with "
                f"{ops.get('rsvp_days')} days to the RSVP deadline.",
                "event:curve-2027", ["event:curve-2027"]))

        # --- program risk: too few confirmed speakers ---
        if "speaker_gap" in ops.get("blockers", []):
            risks.append(self._risk("risk:speaker-gap", "program", "high",
                f"Speaker gap: only {ops.get('confirmed_speakers')} of {ops.get('target_speakers')} "
                "speakers confirmed (no keynote locked).",
                "event:curve-2027", ["event:curve-2027"]))

        # --- perspective risk: missing community voices / imbalance ---
        for cid in gap.get("missing_communities", []):
            risks.append(self._risk(f"risk:missing-{cid.split(':')[-1]}", "perspective", "medium",
                f"Missing perspective: no confirmed attendee from {self._title(ctx, cid)}.",
                cid, [cid]))
        for cid in gap.get("over_represented", []):
            risks.append(self._risk(f"risk:imbalance-{cid.split(':')[-1]}", "perspective", "high",
                f"Viewpoint imbalance: {self._title(ctx, cid)} exceeds the 35% balance limit "
                f"(largest bloc {gap.get('max_share',0):.0%}).",
                "event:curve-2027", [cid]))

        # --- relationship / RSVP risk: VIP non-responses ---
        for r in inv.get("rsvp_risks", []):
            risks.append(self._risk(f"risk:rsvp-{(r.get('person') or 'vip').split(':')[-1]}", "relationship", "medium",
                f"VIP unresponsive: {self._title(ctx, r.get('person'))} unanswered {r.get('days')}d — relationship + RSVP risk.",
                r.get("person"), [r.get("invitation")]))

        # --- data-quality risk: incomplete profiles on people who matter ---
        for pid in rel.get("data_quality_alerts", []):
            risks.append(self._risk(f"risk:data-{pid.split(':')[-1]}", "data_quality", "low",
                f"Data quality: {self._title(ctx, pid)} has an incomplete Attio profile.",
                pid, [pid]))

        # --- follow-up risk: overdue follow-ups ---
        for fid in f("post_event_knowledge").get("overdue_followups", []):
            risks.append(self._risk(f"risk:followup-{fid.split(':')[-1]}", "follow_up", "medium",
                f"Overdue follow-up: {self._title(ctx, fid)}.", fid, [fid]))

        # --- decision risk: keynote unselected ---
        risks.append(self._risk("risk:decision-keynote", "decision", "high",
            "Unmade decision: keynote speaker for The Curve 2027 is not selected — owner & deadline undefined.",
            "event:curve-2027", ["risk:speaker-gap"]))

        # --- strategic + governance risks (Memory + Rules / goals) ---
        goals = {g["id"]: g for g in ctx["goals"]}
        # Frontier-connections goal exposed if a frontier lab has no confirmed attendee.
        for oid in gap.get("missing_orgs", []):
            if oid.startswith("lab:"):
                risks.append(self._risk("risk:strategic-frontier", "strategic", "medium",
                    f"Company goal “Build stronger connections across frontier AI labs” exposed — "
                    f"{self._title(ctx, oid)} has no confirmed attendee.",
                    "goal:company-frontier-connections", [oid]))
        # Viewpoint-diversity goal exposed by imbalance.
        if gap.get("over_represented"):
            risks.append(self._risk("risk:strategic-diversity", "strategic", "medium",
                "Company goal “Improve diversity of viewpoints” exposed by current attendee imbalance.",
                "goal:company-viewpoint-diversity", gap.get("over_represented", [])))
        # Governance: goals awaiting human ratification.
        for g in ctx["goals"]:
            if g["status"] == "draft":
                risks.append(self._risk(f"risk:goal-draft-{g['id'].split(':')[-1]}", "governance", "low",
                    f"Goal awaiting ratification: “{g['title']}” ({g['data'].get('owner_role')}).",
                    g["id"], [g["id"]]))

        by_type: dict[str, int] = {}
        for r in risks:
            by_type[r["risk_type"]] = by_type.get(r["risk_type"], 0) + 1
        bullets = [f"[{r['severity'].upper()}/{r['risk_type']}] {r['title']}" for r in risks]
        headline = (f"Risk Watcher: {len(risks)} cross-functional risk(s) — "
                    + ", ".join(f"{n} {t}" for t, n in by_type.items()) + ".")
        return {"headline": headline, "bullets": bullets, "risks": risks, "by_type": by_type}

    def _risk(self, rid, rtype, severity, title, affects, evidence) -> dict[str, Any]:
        return {"id": rid, "risk_type": rtype, "severity": severity, "title": title,
                "affects": affects, "evidence": evidence}

    def _title(self, ctx: dict[str, Any], node_id: str | None) -> str:
        if not node_id:
            return "—"
        n = next((x for x in ctx["people"] + ctx["communities"] + ctx["organizations"] + ctx["ai_labs"]
                  + ctx["follow_ups"] if x["id"] == node_id), None)
        return n["title"] if n else node_id
