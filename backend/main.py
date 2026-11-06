"""Campus Customs backend (FastAPI) for the React dashboard.

Start it from the backend/ folder (with the hw5 venv active):

    uvicorn main:app --reload --port 8000

Routes (all JSON):
    GET  /api/health                         is the backend up, which model, is a key set
    GET  /api/tickets                        the tickets and whether each is open or resolved
    GET  /api/tickets/{id}                   one ticket
    POST /api/tickets/{id}/run               run the agent team on that ticket (background)
    GET  /api/runs/{run_id}                  status and result of a run
    GET  /api/events                         recent agent events: who said what, which tools
    GET  /api/approvals                      what the agents prepared for a human to approve
    POST /api/approvals/{approval_id}/approve  a human approves one of those -> money moves
    POST /api/approve                        a human approves a payment/purchase typed in directly
    GET  /api/cash                           current checking balance (cash_accounts)
    POST /api/reset                          reset the working DB from the original

Shop data is read and written only through the campus-customs MCP server. Agents can only
prepare payments; the two approve routes are the only places cash changes, and they need a
named person in approved_by.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# `uvicorn main:app` runs from backend/, so put hw5/ on the path and import the package.
HW5_DIR = Path(__file__).resolve().parent.parent
if str(HW5_DIR) not in sys.path:
    sys.path.insert(0, str(HW5_DIR))

from backend.audit import append_event, now_utc  # noqa: E402
from backend.config import AUDIT_TRAIL, DB_PATH, MODEL_NAME, ORIGINAL_DB  # noqa: E402
from backend.models import AGENTS, AuditEvent  # noqa: E402
from backend.run_team import reset_working_db  # noqa: E402
from backend.shop_mcp import shop_toolset  # noqa: E402
from backend.team import new_run_id, run_ticket  # noqa: E402


# --- MCP connection --------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with shop_toolset():  # one MCP server process for the life of the backend
        yield


app = FastAPI(title="Campus Customs backend", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",  # the React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


async def mcp(tool: str, **args: Any) -> Any:
    """Call a campus-customs MCP tool. Tool refusals become HTTP errors with the tool's message."""
    try:
        return await shop_toolset().direct_call_tool(tool, args)
    except Exception as exc:  # the MCP tool raised ToolError (pydantic-ai surfaces it as ModelRetry)
        msg = str(exc)
        if "not in" in msg:
            code = 404
        elif msg.startswith("Refused") or "already paid" in msg:
            code = 409
        else:
            code = 400
        raise HTTPException(status_code=code, detail=msg) from exc


def audit_human(event: str, data: dict[str, Any], ticket_id: int | None = None, run_id: str = "human") -> None:
    append_event(AuditEvent(ts=now_utc(), run_id=run_id, ticket_id=ticket_id, agent="human",
                            chain=["human"], step=0, event=event, data=data))


def read_audit() -> list[dict[str, Any]]:
    if not AUDIT_TRAIL.exists() or AUDIT_TRAIL.stat().st_size == 0:
        return []
    return json.loads(AUDIT_TRAIL.read_text(encoding="utf-8"))


# --- health ----------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "ok": True,
        "model": MODEL_NAME,
        "portkey_key_set": bool(os.getenv("PORTKEY_API_KEY", "").strip()),
        "database": str(DB_PATH.relative_to(HW5_DIR)) if DB_PATH.is_relative_to(HW5_DIR) else str(DB_PATH),
        "run_in_progress": ACTIVE["run_id"],
    }


# --- tickets ---------------------------------------------------------------------------

@app.get("/api/tickets")
async def list_tickets() -> list[dict[str, Any]]:
    """Every ticket with `state` = open or resolved (status keeps the finer board status)."""
    tickets = await mcp("list_tickets")
    return [{**t, "state": "resolved" if t["resolved"] else "open"} for t in tickets]


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict[str, Any]:
    t = await mcp("get_ticket", ticket_id=ticket_id)
    return {**t, "state": "resolved" if t["status"] == "resolved" else "open"}


# --- runs ------------------------------------------------------------------------------

RUNS: dict[str, dict[str, Any]] = {}
ACTIVE: dict[str, Any] = {"run_id": None}  # one team run at a time: keeps spend and cash planning sane
_TASKS: set[asyncio.Task] = set()


async def _do_run(run_id: str, ticket_id: int) -> None:
    run = RUNS[run_id]
    try:
        run["result"] = await run_ticket(ticket_id, run_id=run_id)
        run["status"] = "done"
        # The run finished: mark the ticket resolved on the board, with the Boss's call as the note.
        # Anything a person still has to approve stays in the approvals queue.
        decision = run["result"]["decision"]
        pending = len(decision.get("approvals_needed", []))
        note = f"Agent team finished (run {run_id}): {decision.get('decision', '')}".strip()
        if pending:
            note += f" [{pending} item(s) waiting for human approval]"
        await mcp("update_ticket_status", ticket_id=ticket_id, status="resolved", note=note[:1000])
    except Exception as exc:
        run["status"] = "error"
        run["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        run["finished_at"] = now_utc()
        ACTIVE["run_id"] = None


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_team_on_ticket(ticket_id: int, wait: bool = False) -> dict[str, Any]:
    """Start the agent team on one ticket. Returns a run_id right away; poll /api/events
    (or /api/runs/{run_id}) to watch it. Pass ?wait=true to block until it finishes."""
    await mcp("get_ticket", ticket_id=ticket_id)  # 404 if the ticket doesn't exist
    if not os.getenv("PORTKEY_API_KEY", "").strip():
        raise HTTPException(503, "PORTKEY_API_KEY is missing. Add it to hw5/.env and restart the backend.")
    if ACTIVE["run_id"]:
        raise HTTPException(409, f"Run {ACTIVE['run_id']} is still going. Wait for it to finish.")

    run_id = new_run_id()
    ACTIVE["run_id"] = run_id
    RUNS[run_id] = {"run_id": run_id, "ticket_id": ticket_id, "status": "running",
                    "started_at": now_utc(), "finished_at": None, "result": None, "error": None}
    task = asyncio.create_task(_do_run(run_id, ticket_id))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    if wait:
        await task
    return RUNS[run_id]


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} since the backend started (older runs are in /api/events)")
    return RUNS[run_id]


# --- events ----------------------------------------------------------------------------

def _summarize(seq: int, e: dict[str, Any]) -> dict[str, Any]:
    """One audit entry -> what the board needs: who, what they said, which tools."""
    d = e.get("data", {})
    said: str | None = None
    output: dict[str, Any] | None = None  # full structured answer, only on final_output
    delegation: dict[str, Any] | None = None  # who a hand-off went to, on delegation_* events
    if e["event"].startswith("delegation"):
        rep = d.get("report") or {}
        delegation = {"to": d.get("to"), "task": d.get("task"), "status": d.get("status"),
                      "reason": d.get("reason"), "summary": rep.get("summary")}
    tools: list[dict[str, Any]] = []
    tool_results: list[dict[str, Any]] = []
    kind = e["event"]
    if kind == "run_start":
        said = d.get("prompt")
    elif kind == "model_response":
        texts = [p["content"] for p in d.get("parts", []) if p.get("kind") == "text"]
        said = "\n".join(t for t in texts if isinstance(t, str)) or None
        tools = [{"tool": p["tool"], "args": p.get("args")} for p in d.get("parts", [])
                 if p.get("kind") == "tool_call" and p.get("tool") != "final_result"]
    elif kind == "model_request":
        tool_results = [{"tool": p.get("tool"), "result": p.get("content")} for p in d.get("parts", [])
                        if p.get("kind") in ("tool_result", "retry")]
    elif kind == "final_output":
        out = d.get("output", {})
        said = out.get("decision") or out.get("summary")
        output = out
    elif kind in ("delegation_start", "delegation_refused"):
        said = f"→ {AGENTS.get(d.get('to'), {}).get('name', d.get('to'))}: {d.get('task')}"
        if kind == "delegation_refused":
            said += f" (refused: {d.get('reason')})"
    elif kind == "delegation_end":
        rep = d.get("report") or {}
        said = rep.get("summary") or d.get("error")
    elif kind == "error":
        said = d.get("error")
    elif kind == "human_approval":
        if d.get("status") == "approved":
            said = f"{d.get('approved_by')} approved the {d.get('type')}"
        else:
            said = f"{d.get('approved_by')} tried to approve the {d.get('type')}, refused: {d.get('error')}"
    elif kind == "db_reset":
        said = "Database reset to the original values"
    agent = e["agent"]
    return {
        "seq": seq,
        "ts": e["ts"],
        "run_id": e["run_id"],
        "ticket_id": e["ticket_id"],
        "agent": agent,
        "agent_name": AGENTS.get(agent, {}).get("name", "Human" if agent == "human" else agent),
        "chain": e.get("chain", []),
        "step": e.get("step"),
        "event": kind,
        "said": said,
        "tools": tools,
        "tool_results": tool_results,
        "output": output,
        "delegation": delegation,
        "model": e.get("model"),
        "usage": e.get("usage"),
    }


@app.get("/api/tickets/{ticket_id}/summary")
async def ticket_summary(ticket_id: int) -> dict[str, Any]:
    """What each agent did on this ticket's latest run: who asked it, the MCP tools it used,
    who it handed work to, its final answer, and tokens. Agents that weren't called are listed
    as not used, so a lean run is easy to see."""
    entries = read_audit()
    starts = [e for e in entries if e["event"] == "run_start" and e["ticket_id"] == ticket_id
              and e["agent"] == "boss" and e.get("chain") == ["boss"]]
    if not starts:
        return {"ticket_id": ticket_id, "run_id": None, "agents": [], "status": "not_run"}
    run_id = starts[-1]["run_id"]
    run_events = [e for e in entries if e["run_id"] == run_id]

    agents: dict[str, dict[str, Any]] = {
        k: {"agent": k, "name": v["name"], "used": False, "asked_by": [], "tools": {}, "delegated_to": [],
            "refused_delegations": 0, "steps": 0, "input_tokens": 0, "output_tokens": 0,
            "summary": None, "output": None, "error": None}
        for k, v in AGENTS.items()
    }
    for e in run_events:
        a = agents.get(e["agent"])
        if a is None:
            continue
        d = e.get("data", {})
        a["used"] = True
        if e["event"] == "run_start" and len(e.get("chain", [])) > 1:
            a["asked_by"].append(AGENTS[e["chain"][-2]]["name"])
        elif e["event"] == "model_response":
            a["steps"] += 1
            a["input_tokens"] += (d.get("tokens") or {}).get("input") or 0
            a["output_tokens"] += (d.get("tokens") or {}).get("output") or 0
            for p in d.get("parts", []):
                if p.get("kind") == "tool_call" and p.get("tool") not in ("delegate", "final_result"):
                    a["tools"][p["tool"]] = a["tools"].get(p["tool"], 0) + 1
        elif e["event"] == "delegation_start":
            a["delegated_to"].append({"to": d.get("to"), "name": AGENTS.get(d.get("to"), {}).get("name"),
                                      "task": d.get("task")})
        elif e["event"] == "delegation_refused":
            a["refused_delegations"] += 1
        elif e["event"] == "final_output":
            out = d.get("output", {})
            a["output"] = out
            a["summary"] = out.get("decision") or out.get("summary")
        elif e["event"] == "error":
            a["error"] = d.get("error")

    finished = any(e["event"] == "run_end" and e["agent"] == "boss" and e.get("chain") == ["boss"] for e in run_events)
    failed = any(e["event"] == "error" and e["agent"] == "boss" and e.get("chain") == ["boss"] for e in run_events)
    return {
        "ticket_id": ticket_id,
        "run_id": run_id,
        "started_at": starts[-1]["ts"],
        "status": "running" if ACTIVE["run_id"] == run_id else ("error" if failed else ("done" if finished else "stopped")),
        "usage": run_events[-1].get("usage"),
        "agents": list(agents.values()),
    }


@app.get("/api/events")
async def events(
    since: int = Query(-1, description="Only events with seq greater than this (use next_since from the last call)"),
    ticket_id: int | None = None,
    run_id: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Recent agent events from output/audit_trail.json, oldest first. The board polls with
    ?since=<next_since> to get only what's new."""
    entries = read_audit()
    picked = [
        _summarize(i, e) for i, e in enumerate(entries)
        if i > since
        and (ticket_id is None or e.get("ticket_id") == ticket_id)
        and (run_id is None or e.get("run_id") == run_id)
    ][-limit:]
    return {"events": picked, "next_since": len(entries) - 1, "run_in_progress": ACTIVE["run_id"]}


# --- approvals (the only place money moves) --------------------------------------------

class ApproveBody(BaseModel):
    approved_by: str = Field(min_length=2, description="Name of the person approving")


class DirectApproval(BaseModel):
    type: Literal["payment", "purchase_order"]
    approved_by: str = Field(min_length=2)
    account: str = "checking"
    # payment
    kind: Literal["invoice", "rent"] | None = None
    ref_id: int | None = None
    # purchase_order
    vendor_id: int | None = None
    sku: str | None = None
    size: str | None = None
    qty: int | None = None
    ticket_id: int | None = None


def _pending_from_audit() -> list[dict[str, Any]]:
    """Approval requests from the Boss's final decisions, with their status."""
    entries = read_audit()
    done = {e["data"].get("approval_id"): e["data"] for e in entries
            if e["event"] == "human_approval" and e["data"].get("status") == "approved"}
    refused = {e["data"].get("approval_id"): e["data"].get("error") for e in entries
               if e["event"] == "human_approval" and e["data"].get("status") == "refused"}
    out = []
    for e in entries:
        if e["event"] != "final_output" or e["agent"] != "boss":
            continue
        for i, a in enumerate(e["data"].get("output", {}).get("approvals_needed", [])):
            approval_id = f"{e['run_id']}-{i}"
            out.append({
                "approval_id": approval_id,
                "run_id": e["run_id"],
                "ticket_id": e["ticket_id"],
                "proposed_at": e["ts"],
                **a,
                "status": "approved" if approval_id in done else "pending",
                "approved_by": done.get(approval_id, {}).get("approved_by"),
                # why the last signing attempt was refused (vendor blocked, already paid, no cash)
                "last_refusal": None if approval_id in done else refused.get(approval_id),
            })
    return out


def _to_direct(a: dict[str, Any], approved_by: str) -> DirectApproval:
    """Turn an agent's ApprovalRequest.ref into the fields the MCP pay tools need."""
    ref = a.get("ref") or {}
    if a["kind"] == "payment":
        kind = ref.get("kind")
        ref_id = ref.get("ref_id")
        if kind is None:  # tolerate {"invoice_id": 501} or {"lease_id": 1}
            if "invoice_id" in ref:
                kind, ref_id = "invoice", ref["invoice_id"]
            elif "lease_id" in ref:
                kind, ref_id = "rent", ref["lease_id"]
        return DirectApproval(type="payment", approved_by=approved_by, kind=kind, ref_id=ref_id,
                              account=ref.get("account", "checking"), ticket_id=a.get("ticket_id"))
    if a["kind"] == "purchase_order":
        return DirectApproval(type="purchase_order", approved_by=approved_by, vendor_id=ref.get("vendor_id"),
                              sku=ref.get("sku"), size=ref.get("size"), qty=ref.get("qty"),
                              account=ref.get("account", "checking"), ticket_id=a.get("ticket_id"))
    raise HTTPException(400, f"Unknown approval kind {a['kind']!r}")


async def _execute(body: DirectApproval, approval_id: str | None = None) -> dict[str, Any]:
    """Run the human-only MCP tool, record the outcome in the audit trail, return it."""
    if body.type == "payment":
        if body.kind is None or body.ref_id is None:
            raise HTTPException(422, "A payment needs kind ('invoice' or 'rent') and ref_id")
        tool, args = "pay_with_approval", {"kind": body.kind, "ref_id": body.ref_id,
                                           "approved_by": body.approved_by, "account": body.account}
    else:
        if None in (body.vendor_id, body.sku, body.size, body.qty):
            raise HTTPException(422, "A purchase needs vendor_id, sku, size and qty")
        tool, args = "purchase_with_approval", {"vendor_id": body.vendor_id, "sku": body.sku, "size": body.size,
                                                "qty": body.qty, "approved_by": body.approved_by,
                                                "account": body.account}
    record = {"approval_id": approval_id, "type": body.type, "tool": tool, "args": args,
              "approved_by": body.approved_by}
    try:
        result = await mcp(tool, **args)
    except HTTPException as exc:
        audit_human("human_approval", {**record, "status": "refused", "error": exc.detail}, body.ticket_id)
        raise
    audit_human("human_approval", {**record, "status": "approved", "result": result}, body.ticket_id)
    cash = await mcp("get_cash_balances")
    return {"status": "approved", "approval_id": approval_id, "result": result, "cash": cash["accounts"]}


@app.get("/api/approvals")
async def approvals(ticket_id: int | None = None, status: Literal["pending", "approved"] | None = None) -> list[dict[str, Any]]:
    """What the agents prepared for a person to approve (payments, purchases, discounts)."""
    items = _pending_from_audit()
    return [a for a in items
            if (ticket_id is None or a["ticket_id"] == ticket_id) and (status is None or a["status"] == status)]


@app.post("/api/approvals/{approval_id}/approve")
async def approve_prepared(approval_id: str, body: ApproveBody) -> dict[str, Any]:
    """A person clicked Approve on something an agent prepared. Payments and purchases move
    cash here (amounts are re-read from the database, never taken from the agent)."""
    match = [a for a in _pending_from_audit() if a["approval_id"] == approval_id]
    if not match:
        raise HTTPException(404, f"No approval {approval_id}")
    a = match[0]
    if a["status"] == "approved":
        raise HTTPException(409, f"Already approved by {a['approved_by']}")
    if a["kind"] == "discount":  # no money moves; just record the sign-off
        audit_human("human_approval", {"approval_id": approval_id, "type": "discount", "status": "approved",
                                       "approved_by": body.approved_by, "summary": a.get("summary")}, a["ticket_id"])
        return {"status": "approved", "approval_id": approval_id, "result": {"discount": a.get("summary")},
                "cash_changed": False}
    return await _execute(_to_direct(a, body.approved_by), approval_id)


@app.post("/api/approve")
async def approve_direct(body: DirectApproval) -> dict[str, Any]:
    """A person approves a payment (invoice or rent) or a restock purchase by its IDs."""
    return await _execute(body)


# --- cash and reset --------------------------------------------------------------------

@app.get("/api/cash")
async def cash() -> dict[str, Any]:
    """Current checking balance from cash_accounts."""
    data = await mcp("get_cash_balances")
    checking = next((a for a in data["accounts"] if a["account"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts")
    return {"account": "checking", "balance": checking["balance"], "as_of": checking["as_of"], "today": data["today"]}


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    """Copy data/campus_customs.db over data/campus_customs_new.db for a fresh run. The
    original is only read. The audit trail is kept (a reset is logged in it)."""
    if ACTIVE["run_id"]:
        raise HTTPException(409, f"Run {ACTIVE['run_id']} is still going; reset after it finishes")
    reset_working_db()
    audit_human("db_reset", {"from": ORIGINAL_DB.name, "to": DB_PATH.name})
    return {"status": "reset", "tickets": await list_tickets(), "cash": await cash()}
