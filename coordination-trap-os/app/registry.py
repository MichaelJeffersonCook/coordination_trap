"""Static registry for the four-level operating model.

Level 3 — shared service agents: the 8 cross-cutting coordination agents plus
the Golden Gate domain agents (we keep both layers). Some are backed by live
pipeline code (`live: True`); the four new coordination agents are declared
services whose behavior is embodied in the inbox router / escalation logic.

Level 4 — automation: the n8n workflows and the company systems they wire to.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Level 3 — Shared service agents
# ---------------------------------------------------------------------------
SERVICE_AGENTS = [
    # --- the 8 cross-cutting coordination agents ---
    {"key": "status_checker", "name": "Status Checker", "group": "Coordination", "live": True,
     "purpose": "Tracks event/RSVP/readiness status across convenings.",
     "backed_by": "event_operations", "systems": ["Google Sheets", "Attio CRM"]},
    {"key": "dependency_checker", "name": "Dependency Checker", "group": "Coordination", "live": False,
     "purpose": "Flags blocking dependencies (speaker↔venue, invite↔relationship owner).",
     "systems": ["Google Sheets", "Attio CRM"]},
    {"key": "risk_watcher", "name": "Risk Watcher", "group": "Coordination", "live": True,
     "purpose": "Synthesizes cross-functional risk and routes it to the owning role.",
     "backed_by": "risk_watcher", "systems": ["Attio CRM", "Google Sheets", "AI news feeds"]},
    {"key": "decision_agent", "name": "Decision Agent", "group": "Coordination", "live": True,
     "purpose": "Turns decision-risk into human-ready briefs with options & a recommendation.",
     "backed_by": "decision_facilitator", "systems": ["Google Docs"]},
    {"key": "planner", "name": "Planner", "group": "Coordination", "live": True,
     "purpose": "Maintains the goal cascade and program plan; proposes topics & goals.",
     "backed_by": "strategy + topic_development", "systems": ["Google Docs", "AI news feeds"]},
    {"key": "documentation_agent", "name": "Documentation Agent", "group": "Coordination", "live": True,
     "purpose": "Writes decisions, risks, intros & responses back to the Work Graph (memory).",
     "backed_by": "documentation_steward", "systems": ["Google Docs", "Attio CRM"]},
    {"key": "escalation_agent", "name": "Escalation Agent", "group": "Coordination", "live": False,
     "purpose": "Routes high-severity items to the right human and escalates to leadership.",
     "systems": ["Slack", "Email"]},
    {"key": "meeting_agent", "name": "Meeting Agent", "group": "Coordination", "live": False,
     "purpose": "Turns recommended introductions into scheduled conversations.",
     "systems": ["Calendar", "Email"]},

    # --- Golden Gate domain agents (kept as additional Level-3 services) ---
    {"key": "relationship_intelligence", "name": "Relationship Intelligence", "group": "Domain", "live": True,
     "purpose": "Detects job/org changes, emerging influence, and stale profiles.",
     "systems": ["Attio CRM", "Public web"]},
    {"key": "community_intelligence", "name": "Community Intelligence", "group": "Domain", "live": True,
     "purpose": "Maps communities & influence; identifies emerging leaders.",
     "systems": ["AI news feeds", "Research publications"]},
    {"key": "topic_development", "name": "Topic Development", "group": "Domain", "live": True,
     "purpose": "Monitors news/research/policy; proposes topics, themes & speakers.",
     "systems": ["AI news feeds", "Research publications"]},
    {"key": "network_gap", "name": "Network Gap", "group": "Domain", "live": True,
     "purpose": "Analyzes coverage vs targets and the viewpoint-balance principle.",
     "systems": ["Attio CRM"]},
    {"key": "event_matching", "name": "Event Matching", "group": "Domain", "live": True,
     "purpose": "Scores & ranks candidate attendees for an event.",
     "systems": ["Attio CRM", "Google Sheets"]},
    {"key": "invitation", "name": "Invitation", "group": "Domain", "live": True,
     "purpose": "Runs the invitation/RSVP pipeline; flags VIP RSVP risk.",
     "systems": ["Attio CRM", "Email", "Google Sheets"]},
    {"key": "relationship_facilitator", "name": "Relationship Facilitator", "group": "Domain", "live": True,
     "purpose": "Recommends high-value cross-community introductions.",
     "systems": ["Attio CRM"]},
    {"key": "post_event_knowledge", "name": "Post-Event Knowledge", "group": "Domain", "live": True,
     "purpose": "Captures outcomes & follow-ups; updates institutional memory.",
     "systems": ["Google Docs", "Attio CRM"]},
]

# ---------------------------------------------------------------------------
# Level 4 — Systems of record + n8n workflows
# ---------------------------------------------------------------------------
SYSTEMS = [
    {"name": "Attio CRM", "kind": "CRM"},
    {"name": "Google Sheets", "kind": "Planning"},
    {"name": "Google Docs", "kind": "Knowledge"},
    {"name": "Email", "kind": "Comms"},
    {"name": "Slack", "kind": "Comms"},
    {"name": "AI news feeds", "kind": "Signals"},
    {"name": "Research publications", "kind": "Signals"},
    {"name": "Calendar", "kind": "Scheduling"},
    {"name": "Public web", "kind": "Signals"},
]

WORKFLOWS = [
    {"name": "Executive Brief Generation", "file": "executive-brief-generation.workflow.json",
     "trigger": "Schedule · weekday 07:00", "systems": ["Attio CRM", "Google Sheets", "AI news feeds", "Slack"],
     "agents": ["All (full pipeline)"]},
    {"name": "Attio Sync", "file": "attio-sync.workflow.json",
     "trigger": "Schedule · every 6h", "systems": ["Attio CRM", "Slack"],
     "agents": ["relationship_intelligence"]},
    {"name": "Relationship Enrichment", "file": "relationship-enrichment.workflow.json",
     "trigger": "Webhook · Attio record changed", "systems": ["Attio CRM", "Public web", "Slack"],
     "agents": ["relationship_intelligence"]},
    {"name": "Event Matching", "file": "event-matching.workflow.json",
     "trigger": "Webhook · build attendee list", "systems": ["Attio CRM", "Google Sheets", "Slack"],
     "agents": ["event_matching", "network_gap"]},
    {"name": "Topic Development", "file": "topic-development.workflow.json",
     "trigger": "Schedule · weekly", "systems": ["AI news feeds", "Research publications", "Slack"],
     "agents": ["topic_development"]},
    {"name": "Invitation Follow-Up", "file": "invitation-follow-up.workflow.json",
     "trigger": "Schedule · weekday 09:00", "systems": ["Attio CRM", "Email", "Slack"],
     "agents": ["invitation", "escalation_agent"]},
    {"name": "Post-Event Knowledge Capture", "file": "post-event-knowledge-capture.workflow.json",
     "trigger": "Webhook · event closed", "systems": ["Google Docs", "Attio CRM", "Slack"],
     "agents": ["post_event_knowledge", "documentation_agent"]},
    {"name": "Relationship Graph Updates", "file": "relationship-graph-update.workflow.json",
     "trigger": "Schedule · daily", "systems": ["Attio CRM", "Calendar", "Slack"],
     "agents": ["relationship_facilitator", "meeting_agent"]},
]


def service_by_key(key: str) -> dict | None:
    return next((s for s in SERVICE_AGENTS if s["key"] == key), None)
