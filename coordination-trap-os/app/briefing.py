"""Daily Executive Briefing orchestrator.

The heart of the push model. Runs the relationship/event agent pipeline in the
order the book describes and assembles one briefing pushed to Golden Gate's
leaders — no manual pulling from Attio / sheets / news required.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from . import agents, config, context_builder, db
from . import workgraph as wg
from .llm import llm


# Pipeline order: each agent's findings feed the next. network_gap before
# event_matching; ops/invitation/gap before risk_watcher; risk before decisions.
PIPELINE = [
    ("strategy", "STRATEGY"),
    ("relationship_intelligence", "RELATIONSHIP_INTELLIGENCE"),
    ("community_intelligence", "COMMUNITY_INTELLIGENCE"),
    ("topic_development", "TOPIC_DEVELOPMENT"),
    ("network_gap", "NETWORK_GAP"),
    ("event_matching", "EVENT_MATCHING"),
    ("invitation", "INVITATION"),
    ("event_operations", "EVENT_OPERATIONS"),
    ("relationship_facilitator", "RELATIONSHIP_FACILITATOR"),
    ("post_event_knowledge", "POST_EVENT_KNOWLEDGE"),
    ("risk_watcher", "RISK_WATCHER"),
    ("decision_facilitator", "DECISION_FACILITATOR"),
    ("documentation_steward", "DOCUMENTATION_STEWARD"),
]


def run_pipeline() -> tuple[dict[str, Any], dict[str, Any]]:
    """Run the full agent pipeline; return (context, per-agent domain results)."""
    ctx = context_builder.build()
    domain: dict[str, Any] = {}
    for key, attr in PIPELINE:
        domain[key] = _run_with_domain(getattr(agents, attr), ctx, domain)
    return ctx, domain


def generate_daily_brief(persist: bool = True) -> dict[str, Any]:
    ctx, domain = run_pipeline()
    brief = _assemble(ctx, domain)
    if persist:
        bid = f"brief:{uuid.uuid4().hex[:8]}"
        brief["id"] = bid
        with db.session() as conn:
            conn.execute(
                "INSERT INTO briefings (id, created_at, for_date, payload) VALUES (?, ?, ?, ?)",
                (bid, datetime.now(timezone.utc).isoformat(), config.DEMO_TODAY, json.dumps(brief)),
            )
        wg.log_event("executive_briefing", "analysis",
                     f"Generated Daily Executive Briefing for {config.DEMO_TODAY}", data={"brief_id": bid})
    return brief


def _run_with_domain(agent, ctx, domain) -> dict[str, Any]:
    findings = agent.analyze(ctx, domain)
    narrative = llm.narrate(agent.role, agent.instruction, findings)
    return {"agent": agent.name, "role": agent.role, "narrative": narrative, "findings": findings}


def _section(agent_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "agent": agent_result["agent"],
        "narrative": agent_result["narrative"],
        "headline": agent_result["findings"].get("headline"),
        "bullets": agent_result["findings"].get("bullets", []),
    }


def _assemble(ctx: dict[str, Any], domain: dict[str, Any]) -> dict[str, Any]:
    people = context_builder.person_lookup(ctx)
    name = lambda pid: people.get(pid, {}).get("title", pid)

    inv = domain["invitation"]["findings"]
    gap = domain["network_gap"]["findings"]
    comm = domain["community_intelligence"]["findings"]
    fac = domain["relationship_facilitator"]["findings"]
    pek = domain["post_event_knowledge"]["findings"]
    risks = domain["risk_watcher"]["findings"]["risks"]
    briefs = domain["decision_facilitator"]["findings"]["briefs"]

    # Key attendees: confirmed (accepted) people, highest influence first.
    accepted = []
    for invitation in ctx["invitations"]:
        if invitation["status"] == "accepted":
            pid = next((e["dst"] for e in ctx["edges"] if e["src"] == invitation["id"] and e["rel"] == "sent_to"), None)
            if pid and pid in people:
                accepted.append(people[pid])
    accepted.sort(key=lambda p: p["data"].get("influence", 0), reverse=True)
    key_attendees = [{"name": p["title"], "role": p["data"].get("role"),
                      "community": context_builder.community_of_person(ctx, p["id"])} for p in accepted[:6]]

    return {
        "title": "Daily Executive Briefing",
        "org": "Golden Gate Institute for AI",
        "for_date": config.DEMO_TODAY,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "prepared_for": "Steve Newman · Taren Stinebrickner-Kauffman · Jon Finley",
        "event_focus": "The Curve 2027 — Future of Frontier AI Governance",
        "what_changed_since_yesterday": [
            {"summary": e["summary"], "actor": e["actor"], "node_id": e["node_id"]}
            for e in ctx["recent_changes"] if e["kind"] == "observation"
        ],
        "event_readiness": _section(domain["event_operations"]),
        "invitation_status": _section(domain["invitation"]),
        "rsvp_risks": [{"person": name(r.get("person")), "days": r.get("days"),
                        "owner": name(r.get("owner"))} for r in inv.get("rsvp_risks", [])],
        "missing_perspectives": _section(domain["network_gap"]),
        "key_attendees": key_attendees,
        "emerging_leaders": [{"name": name(pid),
                              "note": people.get(pid, {}).get("data", {}).get("note", "")}
                             for pid in comm.get("emerging_leaders", [])],
        "ai_ecosystem_developments": _section(domain["topic_development"]),
        "recommended_introductions": [{"a": name(i["a"]), "b": name(i["b"]), "reason": i["reason"]}
                                      for i in fac.get("introductions", [])],
        "follow_up_opportunities": [{"title": f["title"], "due": f["due"], "owner": name(f["owner"]),
                                     "status": f["status"]} for f in pek.get("followup_opportunities", [])],
        "new_risks": [{"id": r["id"], "type": r["risk_type"], "severity": r["severity"],
                       "title": r["title"], "affects": r["affects"]} for r in risks],
        "decisions_needed": briefs,
        "recommended_actions": _recommended_actions(domain, name),
        "items_requiring_approval": _open_approvals(),
        "strategic_goals": {**_section(domain["strategy"]), "goal_tree": ctx["goal_tree"]},
        "agent_trace": [
            {"step": i + 1, "agent": d["agent"], "role": d["role"], "headline": d["findings"].get("headline")}
            for i, d in enumerate(domain.values())
        ],
    }


def _recommended_actions(domain: dict[str, Any], name) -> list[dict[str, str]]:
    actions = []
    for b in domain["decision_facilitator"]["findings"].get("briefs", []):
        actions.append({"action": f"Make decision: {b['issue']}", "owner": b["owner_role"],
                        "due": b["deadline"], "why": "Recommendation ready; needs human sign-off."})
    for r in domain["invitation"]["findings"].get("rsvp_risks", []):
        actions.append({"action": f"Personal follow-up to {name(r.get('person'))} (VIP, unanswered {r.get('days')}d)",
                        "owner": name(r.get("owner")), "due": "2027-04-24",
                        "why": "VIP RSVP at risk; relationship-owner outreach beats a reminder email."})
    recs = domain["network_gap"]["findings"].get("recommended_invitees", [])
    if recs:
        actions.append({"action": "Approve targeted invites to missing-voice candidates: " +
                        ", ".join(name(r["person"]) for r in recs),
                        "owner": "President", "due": "2027-04-27",
                        "why": "Restores viewpoint balance before the list is finalized."})
    return actions


def _open_approvals() -> list[dict[str, Any]]:
    with db.session() as conn:
        rows = conn.execute("SELECT * FROM approvals WHERE status = 'pending' ORDER BY created_at DESC").fetchall()
    return [{"id": r["id"], "owner_role": r["owner_role"], "title": r["title"],
             "detail": r["detail"], "related_node": r["related_node"], "status": r["status"]} for r in rows]
