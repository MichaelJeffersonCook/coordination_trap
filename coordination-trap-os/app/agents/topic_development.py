"""Topic Development Agent — identifies important topics for future events.

Monitors AI news, policy developments, research publications, and frontier-lab
activity; recommends event topics, themes, and speakers.
"""
from __future__ import annotations

from typing import Any

from .base import Agent


class TopicDevelopmentAgent(Agent):
    name = "topic_development"
    role = "Topic Development Agent"
    instruction = ("Monitor AI news, policy, research and frontier labs; recommend event "
                   "topics, dinner/salon themes, and speakers.")

    def analyze(self, ctx: dict[str, Any], domain: dict[str, Any] | None = None) -> dict[str, Any]:
        pubs = ctx["publications"]
        policies = ctx["policy_initiatives"]
        topics = ctx["topics"]

        # Topics gaining heat, plus explicitly-proposed topics.
        hot_topics = [t for t in topics if t["data"].get("heat") in ("high", "rising")]
        proposed = [t for t in topics if t["status"] == "proposed"]

        # Suggested speakers: people connected to hot publications / policy via related_to.
        suggested_speakers: list[str] = []
        for src in pubs + policies:
            if src["data"].get("heat") in ("high", "rising"):
                for e in ctx["edges"]:
                    if e["src"] == src["id"] and e["rel"] == "related_to" and e["dst"].startswith("person:"):
                        suggested_speakers.append(e["dst"])
        suggested_speakers = sorted(set(suggested_speakers))

        people = {p["id"]: p["title"] for p in ctx["people"]}
        bullets: list[str] = []
        for t in proposed:
            bullets.append(f"PROPOSED TOPIC: {t['title']} (rising heat) — candidate Curve session / dinner theme.")
        for src in pubs + policies:
            if src["data"].get("heat") in ("high", "rising"):
                bullets.append(f"SIGNAL: {src['title']} ({src['data'].get('venue', src['data'].get('jurisdiction',''))}).")
        if suggested_speakers:
            bullets.append("Suggested speakers from current signals: " +
                           ", ".join(people.get(s, s) for s in suggested_speakers) + ".")

        headline = (f"Topic development: {len(hot_topics)} hot topic(s), {len(proposed)} new theme(s) proposed, "
                    f"{len(suggested_speakers)} speaker(s) suggested from this week's signals.")
        return {
            "headline": headline, "bullets": bullets,
            "recommended_topics": [t["id"] for t in hot_topics + proposed],
            "session_proposals": [t["title"] for t in proposed],
            "suggested_speakers": suggested_speakers,
        }
