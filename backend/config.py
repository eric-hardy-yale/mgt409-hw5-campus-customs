"""Settings for the Campus Customs agent team.

- One model for every agent: gpt-6-luna through Portkey (PORTKEY_API_KEY). There is no
  override, on purpose: the shop rule is gpt-6-luna only.
- Paths: working database, MCP server, prompts folder, audit trail.
- Limits that keep a ticket run (and its token bill) bounded.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

BACKEND_DIR = Path(__file__).resolve().parent
HW5_DIR = BACKEND_DIR.parent
load_dotenv(HW5_DIR / ".env")
os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

# --- model -----------------------------------------------------------------------
MODEL_NAME = "gpt-6-luna"  # the only model any agent may use
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# --- paths -----------------------------------------------------------------------
PROMPTS_DIR = BACKEND_DIR / "prompts"
ORIGINAL_DB = HW5_DIR / "data" / "campus_customs.db"  # never written; only copied for a reset
DB_PATH = Path(os.getenv("CAMPUS_CUSTOMS_DB", HW5_DIR / "data" / "campus_customs_new.db"))
MCP_PYTHON = HW5_DIR / ".venv" / "bin" / "python"
MCP_SERVER = HW5_DIR / "mcp_server" / "server.py"
AUDIT_TRAIL = Path(os.getenv("AUDIT_TRAIL_PATH", HW5_DIR / "output" / "audit_trail.json"))

# --- limits (token and loop guardrails) ------------------------------------------
MAX_DELEGATION_DEPTH = 3       # Boss -> A -> B -> C at most
MAX_DELEGATIONS_PER_RUN = 8    # total hand-offs across the whole team for one ticket
MAX_OUTPUT_TOKENS = 6_000      # per model response (includes reasoning tokens)
TOOL_RESULT_CHARS_IN_AUDIT = 2_000  # long tool results are cut in the audit file, not for the agent

# Shared across every agent in one ticket run (delegated runs add to the same usage).
TEAM_LIMITS = UsageLimits(
    request_limit=40,           # model calls for the whole team
    tool_calls_limit=60,        # MCP + delegate calls for the whole team
    total_tokens_limit=250_000,
)


def require_api_key() -> str:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        raise RuntimeError("PORTKEY_API_KEY is missing. Copy .env.example to hw5/.env and add your key.")
    return key


@lru_cache(maxsize=1)
def build_model() -> OpenAIResponsesModel:
    """The one shared model. Built on first use so imports work before a key is set."""
    client = AsyncOpenAI(base_url=PORTKEY_BASE_URL, api_key=require_api_key())
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def load_prompt(agent_key: str) -> str:
    return (PROMPTS_DIR / f"{agent_key}.md").read_text(encoding="utf-8").strip()
