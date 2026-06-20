"""LLM abstraction layer.

Agents do their *analysis* deterministically by querying the Work Graph (that
is what makes the demo reproducible and what real monitoring agents do). They
use this layer only to turn structured findings into human-readable narrative.

Providers:
  - "mock"      : deterministic, no API key, default. Fully runnable offline.
  - "anthropic" : Claude via the official `anthropic` SDK (ANTHROPIC_API_KEY).
  - "openai"    : OpenAI via the official `openai` SDK (OPENAI_API_KEY).

Switch globally with CTOS_LLM_PROVIDER, or per-call via narrate(..., provider=).
If a real provider errors or its SDK/key is missing, we fall back to mock so the
prototype never breaks. Model defaults follow the Anthropic guidance: Claude
Opus 4.8 (`claude-opus-4-8`) with adaptive thinking available; no temperature /
budget_tokens (removed on 4.8).
"""
from __future__ import annotations

from typing import Any

from . import config

SYSTEM_PREFIX = (
    "You are an organizational-service agent inside an AI-native product "
    "operating system (not a chatbot). You receive structured findings already "
    "computed from the systems of record and turn them into a concise, factual "
    "briefing paragraph for a busy human. No preamble, no fluff, no restating "
    "the question — lead with the most decision-relevant point."
)


class LLMClient:
    def __init__(self) -> None:
        self.provider = config.LLM_PROVIDER

    def narrate(self, role: str, instruction: str, findings: dict[str, Any],
                provider: str | None = None) -> str:
        """Turn structured findings into a short narrative paragraph."""
        prov = (provider or self.provider).lower()
        if prov == "anthropic":
            return self._anthropic(role, instruction, findings)
        if prov == "openai":
            return self._openai(role, instruction, findings)
        return self._mock(role, instruction, findings)

    # -- mock provider (deterministic) --------------------------------------
    def _mock(self, role: str, instruction: str, findings: dict[str, Any]) -> str:
        headline = findings.get("headline")
        bullets = findings.get("bullets", [])
        parts: list[str] = []
        if headline:
            parts.append(headline)
        parts.extend(f"• {b}" for b in bullets)
        if not parts:
            parts.append(f"{role}: no notable signals.")
        return "\n".join(parts)

    # -- prompt shared by real providers ------------------------------------
    def _user_prompt(self, role: str, instruction: str, findings: dict[str, Any]) -> str:
        import json

        return (
            f"Your role: {role}.\nYour standing instruction: {instruction}\n\n"
            f"Structured findings (already computed from the systems of record):\n"
            f"{json.dumps(findings, indent=2, default=str)}\n\n"
            "Write the briefing paragraph now."
        )

    # -- Anthropic (Claude) -------------------------------------------------
    def _anthropic(self, role: str, instruction: str, findings: dict[str, Any]) -> str:
        try:
            import anthropic

            # Anthropic() resolves ANTHROPIC_API_KEY (or an `ant` profile) from
            # the environment; only pass an explicit key if one is configured.
            client = (anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
                      if config.ANTHROPIC_API_KEY else anthropic.Anthropic())
            msg = client.messages.create(
                model=config.ANTHROPIC_MODEL,   # claude-opus-4-8
                max_tokens=1024,
                system=SYSTEM_PREFIX,
                messages=[{"role": "user",
                           "content": self._user_prompt(role, instruction, findings)}],
                # No temperature / budget_tokens — removed on Opus 4.8. Adaptive
                # thinking is available via thinking={"type":"adaptive"} but this
                # narration is simple summarization, so we leave it off.
            )
            text = next((b.text for b in msg.content if b.type == "text"), "")
            return text or self._mock(role, instruction, findings)
        except Exception as exc:  # graceful fallback keeps the prototype alive
            return self._mock(role, instruction, findings) + f"\n[anthropic unavailable — using mock: {exc}]"

    # -- OpenAI -------------------------------------------------------------
    def _openai(self, role: str, instruction: str, findings: dict[str, Any]) -> str:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=config.OPENAI_API_KEY) if config.OPENAI_API_KEY else OpenAI()
            resp = client.chat.completions.create(
                model=config.OPENAI_MODEL,
                messages=[{"role": "system", "content": SYSTEM_PREFIX},
                          {"role": "user", "content": self._user_prompt(role, instruction, findings)}],
            )
            return resp.choices[0].message.content or self._mock(role, instruction, findings)
        except Exception as exc:
            return self._mock(role, instruction, findings) + f"\n[openai unavailable — using mock: {exc}]"


# Module-level singleton.
llm = LLMClient()
