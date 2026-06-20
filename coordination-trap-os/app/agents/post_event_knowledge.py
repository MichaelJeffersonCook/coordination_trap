"""Post-Event Knowledge Agent — captures organizational learning.

Processes event notes and follow-ups, records introductions made, and surfaces
open/overdue follow-up opportunities to keep institutional memory current.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class PostEventKnowledgeAgent(Agent):
    name = "post_event_knowledge"
    role = "Post-Event Knowledge Agent"
    instruction = ("Capture event outcomes, record introductions and follow-ups, and surface "
                   "open/overdue follow-up opportunities.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        follow_ups = ctx["follow_ups"]
        people = cb.person_lookup(ctx)
        open_fu = [f for f in follow_ups if f["status"] == "open"]
        overdue = [f for f in follow_ups if f["status"] == "overdue"]
        intros_made = [i for i in ctx["introductions"] if i["status"] == "made"]

        bullets = []
        for f in overdue:
            bullets.append(f"OVERDUE follow-up: {f['title']} (due {f['data'].get('due')}, owner "
                           f"{people.get(f['data'].get('owner'),{}).get('title','—')}).")
        for f in open_fu:
            bullets.append(f"Open follow-up: {f['title']} (due {f['data'].get('due')}).")
        for i in intros_made:
            bullets.append(f"On record: {i['title']}.")

        headline = (f"Institutional memory: {len(overdue)} overdue and {len(open_fu)} open follow-up(s); "
                    f"{len(intros_made)} past introduction(s) on record.")
        return {
            "headline": headline, "bullets": bullets,
            "open_followups": [f["id"] for f in open_fu],
            "overdue_followups": [f["id"] for f in overdue],
            "followup_opportunities": [
                {"id": f["id"], "title": f["title"], "due": f["data"].get("due"),
                 "owner": f["data"].get("owner"), "status": f["status"]}
                for f in overdue + open_fu
            ],
        }
