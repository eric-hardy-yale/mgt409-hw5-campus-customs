"""Data types for the Campus Customs agent team.

- AgentKey / AGENTS: the five roles and what each one owns
- Fact, ApprovalRequest, AgentReport: what a teammate hands back when work is delegated to it
- TicketDecision: the Boss's final call on a ticket
- AuditEvent: one line of output/audit_trail.json
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

AgentKey = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]

AGENTS: dict[str, dict[str, str]] = {
    "boss": {
        "name": "Boss",
        "role": "Reads each ticket, decides who works on it, and makes the final call.",
    },
    "inventory": {
        "name": "Inventory",
        "role": "Checks stock by SKU and size, spots shortfalls, finds which vendor can restock and when.",
    },
    "accounting": {
        "name": "Accounting",
        "role": "Watches cash and invoices, checks margins and discounts, prepares payments and purchase orders for human approval.",
    },
    "facilities": {
        "name": "Facilities",
        "role": "Handles the shop space: leases, rent due dates, landlord notices.",
    },
    "customer_service": {
        "name": "Customer Service",
        "role": "Drafts messages to customers and other requesters. Drafts stay on the board; nothing is sent.",
    },
}

TicketStatus = Literal["open", "in_progress", "waiting_on_human", "resolved"]


class Fact(BaseModel):
    """One fact the agent relied on, with the MCP tool (or teammate) it came from."""

    detail: str = Field(description="The fact in plain words, with the exact number or date")
    source: str = Field(description="MCP tool name that returned it, e.g. check_stock, or 'from Inventory'")


class ApprovalRequest(BaseModel):
    """Something only a person can OK: a payment, a purchase order, or a discount."""

    kind: Literal["payment", "purchase_order", "discount"]
    summary: str = Field(description="What is being approved, e.g. 'Pay invoice 501, $840 to Bulldog Print Co'")
    amount: float | None = Field(default=None, description="Dollar amount from the database, if any")
    ref: dict[str, Any] = Field(
        default_factory=dict,
        description="IDs needed to act on it, e.g. {'kind': 'invoice', 'ref_id': 501, 'account': 'checking'}",
    )
    reason: str = Field(description="Why it is needed for this ticket")


class AgentReport(BaseModel):
    """What a specialist hands back to whoever delegated to it."""

    agent: AgentKey
    summary: str = Field(description="Two or three sentences answering the task you were given")
    facts: list[Fact] = Field(default_factory=list)
    recommendation: str = Field(description="What you think should happen next")
    approvals_needed: list[ApprovalRequest] = Field(default_factory=list)
    customer_draft: str | None = Field(default=None, description="Draft message, only Customer Service fills this")
    open_questions: list[str] = Field(default_factory=list, description="Anything you couldn't settle from the data")


class TicketDecision(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    decision: str = Field(description="The final call in a few sentences")
    agents_used: list[AgentKey] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    approvals_needed: list[ApprovalRequest] = Field(default_factory=list)
    customer_draft: str | None = None
    next_status: TicketStatus = Field(description="Where the ticket stands now")


class AuditEvent(BaseModel):
    """One entry in output/audit_trail.json."""

    ts: str  # wall-clock UTC time of the event
    run_id: str
    ticket_id: int | None
    agent: AgentKey | Literal["human"]  # "human" = an approval or reset from the dashboard
    chain: list[str]  # who delegated to whom to get here, e.g. ["boss", "inventory"]
    step: int  # step number inside this agent's loop
    event: Literal[
        "run_start",           # an agent loop starts (prompt it was given)
        "model_request",       # what goes to the model this step (prompt, tool results, retries)
        "model_response",      # what the model sent back (tool calls with args, text, tokens)
        "delegation_start",    # an agent hands a task to a teammate
        "delegation_end",      # the teammate's report comes back
        "delegation_refused",  # a hand-off blocked by a guardrail (loop, depth, budget)
        "final_output",        # the agent's structured answer
        "run_end",
        "error",
        "human_approval",      # a person approved (or tried to approve) a payment, purchase or discount
        "db_reset",            # a person reset the working database from the original
    ]
    model: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, int] | None = None  # team-wide usage so far
