"""Smoke test for the campus-customs MCP server.

Starts the server exactly the way hw5/.mcp.json says, calls each tool over MCP
for the ticket it is meant to unlock, checks every answer against a direct SQL
query of the same database, and writes the evidence to output/mcp_smoke.json.

Run from hw5/:  .venv/bin/python mcp_server/smoke_test.py
"""

import asyncio
import hashlib
import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

HW5_DIR = Path(__file__).resolve().parent.parent
DB_PATH = HW5_DIR / "data" / "campus_customs_new.db"
OUT_PATH = HW5_DIR / "output" / "mcp_smoke.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql_one(query: str, params: tuple = ()) -> sqlite3.Row:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(query, params).fetchone()
    finally:
        conn.close()


def expected_stock(sku, size, qty_needed):
    row = sql_one("SELECT qty, location FROM inventory WHERE sku = ? AND size = ?", (sku, size))
    return {"qty_on_hand": row["qty"], "location": row["location"],
            "shortfall": max(qty_needed - row["qty"], 0)}


def expected_rent(lease_id):
    lease = sql_one("SELECT monthly_rent, next_due FROM leases WHERE id = ?", (lease_id,))
    today = sql_one("SELECT date_today FROM desk")["date_today"]
    cash = sql_one("SELECT balance FROM cash_accounts WHERE name = 'checking'")["balance"]
    days = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days
    return {"monthly_rent": lease["monthly_rent"], "next_due": lease["next_due"], "today": today,
            "days_until_due": days, "checking_balance": cash,
            "balance_after_rent": cash - lease["monthly_rent"]}


def expected_price(sku):
    row = sql_one("SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,))
    return {"unit_cost": row["unit_cost"], "list_price": row["list_price"],
            "margin_per_unit": row["list_price"] - row["unit_cost"]}


def pick_actual(tool, data):
    """Pull the fields we compare out of the tool's answer."""
    if tool == "get_rent_status":
        checking = next(a for a in data["cash_accounts"] if a["account"] == "checking")
        return {"monthly_rent": data["monthly_rent"], "next_due": data["next_due"], "today": data["today"],
                "days_until_due": data["days_until_due"], "checking_balance": checking["balance"],
                "balance_after_rent": checking["balance_after_rent"]}
    keys = {"check_stock": ("qty_on_hand", "location", "shortfall"),
            "get_price_and_margin": ("unit_cost", "list_price", "margin_per_unit")}[tool]
    return {k: data[k] for k in keys}


# (ticket, what the ticket asks, tool, arguments, expected answer from SQL)
TICKET_CALLS = [
    (101, "Tauhid Zaman wants 1 CC-TEE-WHITE in S", "check_stock",
     {"sku": "CC-TEE-WHITE", "size": "S", "qty_needed": 1}, lambda: expected_stock("CC-TEE-WHITE", "S", 1)),
    (102, "Elm City Properties rent notice for lease 1", "get_rent_status",
     {"lease_id": 1}, lambda: expected_rent(1)),
    (103, "Yale AI Club wants 20 CC-HOOD-NAVY in M", "check_stock",
     {"sku": "CC-HOOD-NAVY", "size": "M", "qty_needed": 20}, lambda: expected_stock("CC-HOOD-NAVY", "M", 20)),
    (103, "Yale AI Club asks for a bulk discount on CC-HOOD-NAVY", "get_price_and_margin",
     {"sku": "CC-HOOD-NAVY"}, lambda: expected_price("CC-HOOD-NAVY")),
]

# Inputs that aren't in the database: the tool must refuse, not make something up.
NOT_IN_DB_CALLS = [
    ("check_stock", {"sku": "CC-HOOD-NAVY", "size": "XXL"}),
    ("get_rent_status", {"lease_id": 99}),
    ("get_price_and_margin", {"sku": "CC-SOCKS-RED"}),
]


async def main() -> None:
    server = json.loads((HW5_DIR / ".mcp.json").read_text())["mcpServers"]["campus-customs"]
    db_before = sha256(DB_PATH)
    results = []

    transport = StdioTransport(command=server["command"], args=server["args"], cwd=str(HW5_DIR))
    async with Client(transport) as client:
        tools_listed = sorted(t.name for t in await client.list_tools())

        for ticket, asks, tool, args, expected_fn in TICKET_CALLS:
            r = await client.call_tool(tool, args, raise_on_error=False)
            expected = expected_fn()
            actual = None if r.is_error else pick_actual(tool, r.data)
            results.append({
                "ticket": ticket, "ticket_asks": asks, "tool": tool, "arguments": args,
                "response": r.content[0].text if r.is_error else r.data,
                "expected_from_sql": expected,
                "pass": actual == expected,
            })

        for tool, args in NOT_IN_DB_CALLS:
            r = await client.call_tool(tool, args, raise_on_error=False)
            results.append({
                "ticket": None, "ticket_asks": "input not in the database", "tool": tool, "arguments": args,
                "response": r.content[0].text, "expected": "error, no made-up data",
                "pass": r.is_error,
            })

    db_after = sha256(DB_PATH)
    evidence = {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "how": "MCP client over stdio, server launched from hw5/.mcp.json; each answer checked against direct SQL",
        "server": {"name": "campus-customs", "command": server["command"], "args": server["args"]},
        "database": str(DB_PATH.relative_to(HW5_DIR)),
        "tools_listed": tools_listed,
        "calls": results,
        "database_unchanged": db_before == db_after,
        "all_passed": all(c["pass"] for c in results) and db_before == db_after,
    }
    # Keep the vibe coder's own tool-call evidence (Problem 4) if it's already in the file.
    if OUT_PATH.exists():
        previous = json.loads(OUT_PATH.read_text())
        if "vibe_coder_calls" in previous:
            evidence["vibe_coder_calls"] = previous["vibe_coder_calls"]
    OUT_PATH.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"{sum(c['pass'] for c in results)}/{len(results)} calls passed; "
          f"database unchanged: {db_before == db_after}; wrote {OUT_PATH.relative_to(HW5_DIR)}")


if __name__ == "__main__":
    asyncio.run(main())
