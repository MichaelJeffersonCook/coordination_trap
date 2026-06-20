"""Executive rollup.

Rolls the daily briefing UP to the company-goal level for Golden Gate's
leadership: for each company goal, which risks threaten it, the event-readiness
headline, and which decisions need a human owner.
"""
from __future__ import annotations

from typing import Any

from . import context_builder as cb


def build(brief: dict[str, Any]) -> dict[str, Any]:
    ctx = cb.build()
    goals = cb.goals_lookup(ctx)
    company = [g for g in ctx["goals"] if g["data"].get("scope") == "company"]

    def company_targets(affects: str | None, rtype: str) -> list[str]:
        if affects in goals:
            if goals[affects]["data"].get("scope") == "company":
                return [affects]
            return [g for g in cb.aligned_goals(affects)
                    if goals.get(g, {}).get("data", {}).get("scope") == "company"]
        if rtype == "perspective":
            return ["goal:company-viewpoint-diversity"]
        return []

    by_goal: dict[str, list[dict[str, Any]]] = {g["id"]: [] for g in company}
    other_high: list[dict[str, Any]] = []
    for r in brief["new_risks"]:
        hit = [g for g in company_targets(r.get("affects"), r["type"]) if g in by_goal]
        if hit:
            for gid in hit:
                by_goal[gid].append(r)
        elif r["severity"] == "high":
            other_high.append(r)

    sev = {"high": 0, "medium": 1, "low": 2}
    goal_cards = []
    for g in company:
        risks = sorted(by_goal.get(g["id"], []), key=lambda r: sev.get(r["severity"], 3))
        goal_cards.append({
            "goal": g,
            "owner": next((e["dst"] for e in ctx["edges"] if e["src"] == g["id"] and e["rel"] == "owned_by"), None),
            "exposure": "exposed" if any(r["severity"] == "high" for r in risks) else ("watch" if risks else "on_track"),
            "risks": risks,
        })

    ops = brief["event_readiness"]["headline"]
    readiness = "AT RISK"
    for word in ("ON TRACK", "AT RISK", "BEHIND"):
        if word in ops:
            readiness = word
            break
    decisions = [{
        "issue": d["issue"], "owner_role": d["owner_role"], "deadline": d["deadline"],
        "recommendation": d.get("recommendation", ""),
        "needs_exec": d["owner_role"] in ("President", "CEO"),
    } for d in brief["decisions_needed"]]

    people = {p["id"]: p["title"] for p in ctx["people"]}
    return {
        "for_date": brief["for_date"],
        "prepared_for": "Golden Gate leadership — Steve · Taren · Jon",
        "event_focus": brief.get("event_focus"),
        "event_readiness": ops,
        "kpis": {
            "readiness": readiness,
            "confirmed": brief["invitation_status"]["headline"],
            "missing_voices": len(brief["missing_perspectives"]["bullets"]),
            "decisions": len(decisions),
            "approvals": len(brief["items_requiring_approval"]),
        },
        "goal_cards": goal_cards,
        "people": people,
        "decisions": decisions,
        "other_high_risks": other_high,
    }
