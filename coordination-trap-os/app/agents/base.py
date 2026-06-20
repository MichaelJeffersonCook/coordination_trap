"""Base class for organizational-service agents.

Design principle: these are NOT chatbots. Each agent is a service that
monitors the Work Graph, computes structured findings deterministically, and
emits a narrative via the LLM layer. Findings are the machine-readable output
other agents (e.g. Risk Watcher) consume.
"""
from __future__ import annotations

from typing import Any

from ..llm import llm


class Agent:
    name: str = "Agent"
    role: str = "Agent"
    instruction: str = ""

    def analyze(self, ctx: dict[str, Any]) -> dict[str, Any]:
        """Compute structured findings from the context package.

        Subclasses override. Returns a dict with at least:
          headline: str
          bullets: list[str]
          plus any structured fields (risks, decisions, metrics, ...).
        """
        raise NotImplementedError

    def run(self, ctx: dict[str, Any]) -> dict[str, Any]:
        findings = self.analyze(ctx)
        narrative = llm.narrate(self.role, self.instruction, findings)
        return {
            "agent": self.name,
            "role": self.role,
            "narrative": narrative,
            "findings": findings,
        }
