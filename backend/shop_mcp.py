"""The only way agents touch the shop: the campus-customs MCP server.

One stdio connection to mcp_server/server.py (pointed at data/campus_customs_new.db) is
shared by the whole team for a ticket run. Each agent sees only the MCP tools its role
needs. pay_with_approval and purchase_with_approval are never given to any agent: money
only moves through the human approve route in main.py.
"""

from __future__ import annotations

import os
from functools import lru_cache

from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from pydantic_ai import FilteredToolset
from pydantic_ai.mcp import MCPToolset

from .config import DB_PATH, HW5_DIR, MCP_PYTHON, MCP_SERVER

HUMAN_ONLY_TOOLS = {"pay_with_approval", "purchase_with_approval"}

AGENT_MCP_TOOLS: dict[str, set[str]] = {
    "boss": {"list_open_tickets", "get_ticket", "update_ticket_status"},
    "inventory": {"get_ticket", "check_stock", "list_vendors", "prepare_purchase_order"},
    "accounting": {
        "get_ticket", "get_price_and_margin", "list_invoices", "list_vendors",
        "get_cash_balances", "prepare_payment", "prepare_purchase_order",
    },
    "facilities": {"get_ticket", "get_rent_status", "get_cash_balances", "prepare_payment"},
    "customer_service": {"get_ticket", "check_stock", "get_price_and_margin"},
}

assert not any(tools & HUMAN_ONLY_TOOLS for tools in AGENT_MCP_TOOLS.values()), "no agent may pay"


@lru_cache(maxsize=1)
def shop_toolset() -> MCPToolset:
    """The shared MCP connection. Enter it once per ticket run (`async with shop_toolset():`)."""
    transport = StdioTransport(
        command=str(MCP_PYTHON),
        args=[str(MCP_SERVER)],
        cwd=str(HW5_DIR),
        env={**os.environ, "CAMPUS_CUSTOMS_DB": str(DB_PATH)},
    )
    # tool_error_behavior="retry": if the server says "no size XXL", the agent sees that
    # message and can correct itself instead of the whole run crashing.
    return MCPToolset(Client(transport), id="campus-customs", tool_error_behavior="retry", max_retries=2)


def toolset_for(agent_key: str) -> FilteredToolset:
    allowed = AGENT_MCP_TOOLS[agent_key]
    return shop_toolset().filtered(lambda ctx, tool_def: tool_def.name in allowed)
