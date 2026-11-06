"""The Campus Customs agent team (PydanticAI).

Five agents: Boss, Inventory, Accounting, Facilities, Customer Service.
- Every agent runs on gpt-6-luna via Portkey (config.build_model) with its own prompt file
  in backend/prompts/.
- Shop facts come only from the campus-customs MCP server (shop_mcp.toolset_for).
- Full connectivity: every agent has the same `delegate(to, task)` tool and can hand work to
  any other agent. Guardrails stop loops (no handing back to someone already in the chain),
  runaway depth, and runaway spend (team-wide usage limits).
- Every step of every agent loop is appended to output/audit_trail.json.

Entry point: `await run_ticket(101)` -> dict with the Boss's TicketDecision.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from pydantic_ai import Agent, ModelSettings, RunContext, RunUsage

from .audit import append_event, now_utc
from .config import (
    MAX_DELEGATION_DEPTH,
    MAX_DELEGATIONS_PER_RUN,
    MAX_OUTPUT_TOKENS,
    MODEL_NAME,
    PROMPTS_DIR,
    TEAM_LIMITS,
    TOOL_RESULT_CHARS_IN_AUDIT,
    build_model,
    load_prompt,
)
from .models import AGENTS, AgentKey, AgentReport, AuditEvent, TicketDecision
from .shop_mcp import AGENT_MCP_TOOLS, shop_toolset, toolset_for


# --- run state ---------------------------------------------------------------------

@dataclass
class TeamRun:
    """Shared by every agent working one ticket."""

    run_id: str
    ticket_id: int | None
    usage: RunUsage = field(default_factory=RunUsage)  # one bill for the whole team
    delegations: int = 0
    agents_used: list[str] = field(default_factory=list)


@dataclass
class AgentDeps:
    team: TeamRun
    agent: AgentKey
    chain: list[AgentKey]  # e.g. ["boss", "accounting"] while Accounting works for the Boss


def _usage(u: RunUsage) -> dict[str, int]:
    return {
        "requests": u.requests,
        "tool_calls": u.tool_calls,
        "input_tokens": u.input_tokens,
        "output_tokens": u.output_tokens,
    }


def _audit(deps: AgentDeps, step: int, event: str, data: dict[str, Any] | None = None, model: str | None = None) -> None:
    append_event(AuditEvent(
        ts=now_utc(),
        run_id=deps.team.run_id,
        ticket_id=deps.team.ticket_id,
        agent=deps.agent,
        chain=deps.chain,
        step=step,
        event=event,
        model=model,
        data=data or {},
        usage=_usage(deps.team.usage),
    ))


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str, ensure_ascii=False)
    if len(text) <= TOOL_RESULT_CHARS_IN_AUDIT:
        return value
    return text[:TOOL_RESULT_CHARS_IN_AUDIT] + f"... [{len(text) - TOOL_RESULT_CHARS_IN_AUDIT} more chars]"


def _request_parts(parts) -> list[dict[str, Any]]:
    out = []
    for p in parts:
        kind = getattr(p, "part_kind", type(p).__name__)
        if kind == "user-prompt":
            out.append({"kind": "user_prompt", "content": _clip(p.content)})
        elif kind == "tool-return":
            out.append({"kind": "tool_result", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                        "content": _clip(p.content)})
        elif kind == "retry-prompt":
            out.append({"kind": "retry", "tool": p.tool_name, "content": _clip(p.content)})
        else:
            out.append({"kind": kind})
    return out


def _response_parts(parts) -> list[dict[str, Any]]:
    out = []
    for p in parts:
        kind = getattr(p, "part_kind", type(p).__name__)
        if kind == "tool-call":
            out.append({"kind": "tool_call", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                        "args": p.args_as_dict()})
        elif kind == "text":
            out.append({"kind": "text", "content": _clip(p.content)})
        elif kind == "thinking":
            out.append({"kind": "thinking"})  # reasoning text isn't stored, only that it happened
        else:
            out.append({"kind": kind})
    return out


# --- delegation (full connectivity) -----------------------------------------------

async def delegate(ctx: RunContext[AgentDeps], to: AgentKey, task: str) -> str:
    """Hand a task to a teammate and get their report back.

    Any agent can delegate to any other agent. Be specific: include the ticket number and
    exactly what you need (e.g. "Ticket 103: how many CC-HOOD-NAVY in M are on hand and how
    short are we of 20?"). Do not delegate back to someone who is already waiting on you.

    Args:
        to: boss, inventory, accounting, facilities, or customer_service.
        task: The question or job, with the ticket number and any facts they need.
    """
    deps = ctx.deps
    team = deps.team
    refusal = None
    if to not in AGENTS:
        refusal = f"There is no teammate called {to!r}. Use one of: {', '.join(AGENTS)}."
    elif to == deps.agent:
        refusal = "You can't delegate to yourself. Use your own tools."
    elif to in deps.chain:
        refusal = (f"{AGENTS[to]['name']} is already waiting on this chain ({' -> '.join(deps.chain)}). "
                   "Answer with what you have instead of handing it back.")
    elif len(deps.chain) > MAX_DELEGATION_DEPTH:
        refusal = f"Delegation depth limit ({MAX_DELEGATION_DEPTH}) reached. Answer with what you have."
    elif team.delegations >= MAX_DELEGATIONS_PER_RUN:
        refusal = f"Team delegation budget ({MAX_DELEGATIONS_PER_RUN} per ticket) used up. Answer with what you have."
    if refusal:
        _audit(deps, ctx.run_step, "delegation_refused", {"to": to, "task": task, "reason": refusal})
        return f"[delegation refused] {refusal}"

    team.delegations += 1
    _audit(deps, ctx.run_step, "delegation_start", {"to": to, "task": task, "delegation_no": team.delegations})
    caller = AGENTS[deps.agent]["name"]
    prompt = (f"Ticket #{team.ticket_id}. Task from {caller}:\n{task}"
              if team.ticket_id is not None else f"Task from {caller}:\n{task}")
    try:
        report = await run_agent(to, prompt, team, chain=[*deps.chain, to])
    except Exception as exc:
        msg = f"{AGENTS[to]['name']} could not finish: {type(exc).__name__}: {exc}"
        _audit(deps, ctx.run_step, "delegation_end", {"to": to, "status": "error", "error": msg})
        return f"[delegation failed] {msg}"
    _audit(deps, ctx.run_step, "delegation_end", {"to": to, "status": "done", "report": report.model_dump(mode="json")})
    return report.model_dump_json()


# --- the five agents ---------------------------------------------------------------

def _roster(me: str) -> str:
    lines = [f"- {k}: {v['name']} — {v['role']}" for k, v in AGENTS.items() if k != me]
    tools = ", ".join(sorted(AGENT_MCP_TOOLS[me]))
    return (
        "## Your team\n"
        "You can hand work to any teammate with delegate(to=<key>, task=<what you need>):\n"
        + "\n".join(lines)
        + f"\n\n## Your MCP tools\n{tools}\n"
        "These are your only source of shop facts. Never guess a number, date or name."
    )


@lru_cache(maxsize=None)
def get_agent(key: AgentKey) -> Agent:
    output_type = TicketDecision if key == "boss" else AgentReport
    return Agent(
        build_model(),
        name=AGENTS[key]["name"],
        deps_type=AgentDeps,
        output_type=output_type,
        instructions=load_prompt(key) + "\n\n" + _roster(key),
        tools=[delegate],
        toolsets=[toolset_for(key)],
        model_settings=ModelSettings(max_tokens=MAX_OUTPUT_TOKENS),
        retries=2,
    )


def _prompt_fingerprint(key: str) -> dict[str, str]:
    path = PROMPTS_DIR / f"{key}.md"
    return {"prompt_file": f"backend/prompts/{path.name}",
            "prompt_sha256": hashlib.sha256(path.read_bytes()).hexdigest()[:16]}


async def run_agent(key: AgentKey, prompt: str, team: TeamRun, chain: list[AgentKey]) -> AgentReport | TicketDecision:
    """One agent loop: model -> tools (MCP or delegate) -> model ... -> structured output.
    Each step is appended to the audit trail."""
    deps = AgentDeps(team=team, agent=key, chain=chain)
    if key not in team.agents_used:
        team.agents_used.append(key)
    _audit(deps, 0, "run_start", {"prompt": prompt, "mcp_tools": sorted(AGENT_MCP_TOOLS[key]),
                                  **_prompt_fingerprint(key)}, model=MODEL_NAME)
    agent = get_agent(key)
    step = 0  # one step = one model call; its tool calls (and delegations) share the number
    try:
        async with agent.iter(prompt, deps=deps, usage=team.usage, usage_limits=TEAM_LIMITS) as run:
            async for node in run:
                if Agent.is_model_request_node(node):
                    step += 1
                    _audit(deps, step, "model_request", {"parts": _request_parts(node.request.parts)}, model=MODEL_NAME)
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    _audit(deps, step, "model_response", {
                        "parts": _response_parts(resp.parts),
                        "tokens": {"input": resp.usage.input_tokens, "output": resp.usage.output_tokens},
                        "finish_reason": resp.finish_reason,
                    }, model=resp.model_name)
                elif Agent.is_end_node(node):
                    _audit(deps, step, "final_output", {"output": node.data.output.model_dump(mode="json")})
        output = run.result.output
    except Exception as exc:
        _audit(deps, step, "error", {"error": f"{type(exc).__name__}: {exc}"})
        raise
    _audit(deps, step, "run_end", {"steps": step})
    return output


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_ticket(ticket_id: int, run_id: str | None = None) -> dict[str, Any]:
    """Have the Boss work one ticket with the team. Returns the decision plus run info."""
    team = TeamRun(run_id=run_id or new_run_id(), ticket_id=ticket_id)
    prompt = (f"Ticket #{ticket_id} is on the board. Read it with get_ticket, get the facts from the "
              "right teammates, and make the final call.")
    async with shop_toolset():  # one MCP server process for the whole team
        decision = await run_agent("boss", prompt, team, chain=["boss"])
    return {
        "run_id": team.run_id,
        "ticket_id": ticket_id,
        "model": MODEL_NAME,
        "decision": decision.model_dump(mode="json"),
        "agents_used": team.agents_used,
        "delegations": team.delegations,
        "usage": _usage(team.usage),
    }
