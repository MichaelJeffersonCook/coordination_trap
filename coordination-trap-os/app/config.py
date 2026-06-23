"""Central configuration. Reads from environment / .env, with safe defaults
so the prototype runs locally with zero setup."""
from __future__ import annotations

import os
from pathlib import Path

# Optional .env support without adding a hard dependency.
try:  # pragma: no cover - convenience only
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
SEED_DIR = DATA_DIR / "seed"

# Where the Work Graph SQLite database lives.
DB_PATH = Path(os.getenv("CTOS_DB_PATH", PROJECT_DIR / "workgraph.db"))

# LLM provider: "mock" (default, deterministic, no keys) | "anthropic" | "openai".
LLM_PROVIDER = os.getenv("CTOS_LLM_PROVIDER", "mock").lower()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("CTOS_ANTHROPIC_MODEL", "claude-opus-4-8")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("CTOS_OPENAI_MODEL", "gpt-4o")

# "Today" for the prototype. Lets the demo be deterministic regardless of the
# real wall clock. The Curve 2027 scenario sits ~4 weeks before the event.
DEMO_TODAY = os.getenv("CTOS_DEMO_TODAY", "2027-04-21")

# CORS origins allowed to call the API from a browser (e.g. a v0/Vercel front
# end). Comma-separated; "*" allows any origin (fine for a no-auth prototype).
CORS_ORIGINS = [o.strip() for o in os.getenv("CTOS_CORS_ORIGINS", "*").split(",") if o.strip()]
