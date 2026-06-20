"""Event Operations Agent — coordinates event execution.

Tracks attendance vs capacity, speaker confirmation, readiness, and logistics
warnings.
"""
from __future__ import annotations

from typing import Any

from .base import Agent
from .. import context_builder as cb


class EventOperationsAgent(Agent):
    name = "event_operations"
    role = "Event Operations Agent"
    instruction = ("Track attendance vs capacity, speaker confirmation and event readiness; "
                   "raise capacity and logistics warnings.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        event = cb.curve_event(ctx)
        d = event["data"] if event else {}
        days = cb.days_until(d.get("date", ""), ctx["now"])
        rsvp_days = cb.days_until(d.get("rsvp_deadline", ""), ctx["now"])
        accepted = d.get("accepted", 0)
        target = d.get("target_attendance", 250)
        capacity = d.get("capacity", 260)

        speakers = cb.speakers_for(ctx, "event:curve-2027")
        confirmed_speakers = [s for s in speakers if s["status"] == "confirmed"]
        people = cb.person_lookup(ctx)
        confirmed_principals = [s for s in confirmed_speakers
                                if people.get(s["person"], {}).get("data", {}).get("seniority") == "principal"]

        blockers = []
        bullets = [f"{days} days to event; RSVP deadline in {rsvp_days} days.",
                   f"Confirmed {accepted}/{target} attendees (capacity {capacity})."]
        if accepted < target:
            blockers.append("attendance_behind")
            bullets.append(f"BEHIND PACE: {target - accepted} short of target with {rsvp_days} days to the RSVP deadline.")
        bullets.append(f"Speakers: {len(confirmed_speakers)} confirmed / target {d.get('target_speakers',6)} "
                       f"({len(confirmed_principals)} principals).")
        if len(confirmed_speakers) < d.get("target_speakers", 6):
            blockers.append("speaker_gap")

        readiness = "ON TRACK" if not blockers else ("AT RISK" if len(blockers) == 1 else "BEHIND")
        headline = (f"Event readiness for The Curve 2027: {readiness}. {accepted}/{target} confirmed, "
                    f"{len(confirmed_speakers)} speakers locked, {days} days out.")
        return {
            "headline": headline, "bullets": bullets,
            "readiness": readiness, "days_to_event": days, "rsvp_days": rsvp_days,
            "confirmed": accepted, "target": target, "capacity": capacity,
            "confirmed_speakers": len(confirmed_speakers), "target_speakers": d.get("target_speakers", 6),
            "blockers": blockers,
        }
