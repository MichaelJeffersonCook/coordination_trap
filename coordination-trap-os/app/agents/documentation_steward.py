"""Documentation Steward Agent.

Closes the loop: persists agent-produced risks, decision briefs and recommended
introductions back into the Work Graph as nodes + edges, logs events, and raises
human approval requests for anything that requires sign-off. This is how the AI
OS keeps memory and how the push model reaches a human.
"""
from __future__ import annotations

import uuid
from typing import Any

from .base import Agent
from .. import db
from .. import workgraph as wg


class DocumentationStewardAgent(Agent):
    name = "documentation_steward"
    role = "Documentation Steward Agent"
    instruction = "Capture decisions, rationale, risks and recommended introductions; update the Work Graph and memory."

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        domain = domain or {}
        risks = domain.get("risk_watcher", {}).get("findings", {}).get("risks", [])
        briefs = domain.get("decision_facilitator", {}).get("findings", {}).get("briefs", [])
        intros = domain.get("relationship_facilitator", {}).get("findings", {}).get("introductions", [])

        written_risks, written_decisions, approvals, written_intros = [], [], [], []

        for r in risks:
            wg.upsert_node(r["id"], "risk", r["title"], r["severity"],
                           {"risk_type": r["risk_type"], "evidence": r["evidence"]}, actor=self.name)
            if r.get("affects"):
                wg.add_edge(r["id"], "affects", r["affects"])
            written_risks.append(r["id"])

        for b in briefs:
            wg.upsert_node(b["id"], "decision", b["issue"], "pending", b, actor=self.name)
            if b.get("affects"):
                wg.add_edge(b["id"], "affects", b["affects"])
            # A keynote decision resolves the decision-risk it was raised from.
            wg.add_edge(b["id"], "resolves", "risk:decision-keynote")
            wg.log_event(self.name, "decision_brief", f"Prepared decision brief: {b['issue']}", node_id=b["id"])
            written_decisions.append(b["id"])
            if b.get("requires_approval"):
                approvals.append(self._raise_approval(b))

        # Persist recommended introductions as `introduction` nodes (status recommended).
        for i in intros:
            iid = f"intro:{i['a'].split(':')[-1]}-{i['b'].split(':')[-1]}"
            wg.upsert_node(iid, "introduction", f"Introduce {i['a']} ↔ {i['b']}", "recommended",
                           {"reason": i["reason"], "value": i["value"]}, actor=self.name)
            wg.add_edge(iid, "introduced_to", i["a"])
            wg.add_edge(iid, "introduced_to", i["b"])
            written_intros.append(iid)

        headline = (f"Documentation Steward: logged {len(written_risks)} risk(s), "
                    f"{len(written_decisions)} decision brief(s), {len(written_intros)} recommended intro(s), "
                    f"raised {len(approvals)} approval(s).")
        bullets = [f"Wrote {r}" for r in written_risks + written_decisions + written_intros]
        return {
            "headline": headline, "bullets": bullets,
            "risks_written": written_risks, "decisions_written": written_decisions,
            "introductions_written": written_intros, "approvals_raised": approvals,
        }

    def _raise_approval(self, brief: dict[str, Any]) -> str:
        with db.session() as conn:
            existing = conn.execute(
                "SELECT id FROM approvals WHERE related_node = ? AND status = 'pending'",
                (brief["id"],),
            ).fetchone()
            if existing:
                return existing["id"]
            approval_id = f"appr:{uuid.uuid4().hex[:8]}"
            detail = (f"{brief['recommendation']}\n\nOwner: {brief['owner_role']}. Deadline: {brief['deadline']}.")
            conn.execute(
                """INSERT INTO approvals (id, created_at, requested_by, owner_role, title, detail, related_node)
                   VALUES (?, datetime('now'), ?, ?, ?, ?, ?)""",
                (approval_id, self.name, brief["owner_role"],
                 f"Approve recommendation: {brief['issue'][:80]}", detail, brief["id"]),
            )
        wg.log_event(self.name, "approval", f"Raised approval {approval_id} for {brief['owner_role']}",
                     node_id=brief["id"], data={"approval_id": approval_id})
        return approval_id
