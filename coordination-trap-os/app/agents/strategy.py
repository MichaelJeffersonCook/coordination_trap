"""Strategy / Goal Cascade Agent.

Owns the goal cascade in Layer 2. Two jobs:
  1. analyze() — report cascade health for the daily brief (drafts awaiting
     human review, goals with no supporting work, alignment coverage).
  2. propose_cascade() — given a parent goal, DRAFT child goals for the
     responsible roles. Drafts are written as `draft` goal nodes; the human
     owner reviews/edits/approves them (push model: agent proposes, human
     decides).
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import workgraph as wg


class StrategyAgent(Agent):
    name = "strategy"
    role = "Strategy / Goal Cascade Agent"
    instruction = ("Maintain the company→department→role goal cascade. Flag goals "
                   "awaiting human review, goals with no supporting work, and "
                   "misalignment between in-flight work and company goals.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        goals = ctx["goals"]
        drafts = [g for g in goals if g["status"] == "draft"]

        # Company/department goals with no cascaded child goals under them yet.
        has_children = {e["src"] for e in ctx["edges"] if e["rel"] == "cascades_to"}
        company_dept = [g for g in goals if g["data"].get("scope") in ("company", "department")]
        unsupported = [g for g in company_dept if g["id"] not in has_children]

        bullets: list[str] = []
        for g in drafts:
            bullets.append(f"DRAFT awaiting {g['data'].get('owner_role')} review: {g['title']}.")
        for g in unsupported:
            bullets.append(f"No active work ladders into goal: {g['title']} ({g['data'].get('scope')}).")
        if not bullets:
            bullets.append("Cascade healthy: every company/department goal has supporting work and no drafts pending.")

        headline = (f"Strategy: {len(goals)} goals across the cascade — "
                    f"{len(drafts)} draft(s) awaiting human review, "
                    f"{len(unsupported)} goal(s) with no supporting work.")
        return {
            "headline": headline, "bullets": bullets,
            "draft_goals": [g["id"] for g in drafts],
            "unsupported_goals": [g["id"] for g in unsupported],
        }

    def propose_cascade(self, parent_goal_id: str) -> list[dict[str, Any]]:
        """Draft child goals for a parent goal. Deterministic in mock mode.

        Returns the proposed child goal specs (also persisted as `draft` nodes
        with a `cascades_to` edge from the parent), ready for human review.
        """
        parent = wg.get_node(parent_goal_id)
        if not parent:
            return []
        scope = parent["data"].get("scope")
        # company -> department drafts; department -> role drafts.
        child_scope = {"company": "department", "department": "role"}.get(scope)
        if not child_scope:
            return []
        proposals = self._templates(parent, child_scope)
        for p in proposals:
            wg.upsert_node(p["id"], "goal", p["title"], "draft", p["data"])
            wg.add_edge(parent_goal_id, "cascades_to", p["id"])
            if p.get("owner"):
                wg.add_edge(p["id"], "owned_by", p["owner"])
            wg.log_event(self.name, "log", f"Proposed {child_scope} goal (draft): {p['title']}", node_id=p["id"])
        return proposals

    def _templates(self, parent: dict[str, Any], child_scope: str) -> list[dict[str, Any]]:
        base = parent["id"].split(":", 1)[-1]
        return [{
            "id": f"goal:{child_scope}-{base}-draft",
            "title": f"[Proposed] Support “{parent['title']}” at the {child_scope} level",
            "owner": None,
            "data": {"scope": child_scope, "proposed_by": self.name,
                     "parent": parent["id"],
                     "rationale": f"Auto-drafted from {parent['title']}; edit targets and assign an owner before approving."},
        }]
