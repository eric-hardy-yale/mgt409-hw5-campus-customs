"""Run the agent team on tickets from the command line (from hw5/):

    .venv/bin/python -m backend.run_team --ticket 101
    .venv/bin/python -m backend.run_team --all --reset   # full run from the original data

--reset copies data/campus_customs.db over data/campus_customs_new.db first (the original
is only ever read). Every step is appended to output/audit_trail.json; results print as JSON.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from .config import DB_PATH, HW5_DIR, MCP_PYTHON, MCP_SERVER, ORIGINAL_DB
from .team import run_ticket


def reset_working_db() -> None:
    if DB_PATH.resolve() == ORIGINAL_DB.resolve():
        raise SystemExit("Refusing to reset: the working DB path points at the original file")
    shutil.copyfile(ORIGINAL_DB, DB_PATH)
    DB_PATH.chmod(0o644)  # the original is read-only; the copy must be writable


async def open_ticket_ids() -> list[int]:
    """Read the board through the MCP server, like the agents do."""
    transport = StdioTransport(command=str(MCP_PYTHON), args=[str(MCP_SERVER)], cwd=str(HW5_DIR),
                               env={"CAMPUS_CUSTOMS_DB": str(DB_PATH)})
    async with Client(transport) as client:
        result = await client.call_tool("list_open_tickets", {})
    tickets = result.structured_content.get("result", result.structured_content)
    return [t["id"] for t in tickets]


async def main() -> None:
    ap = argparse.ArgumentParser(description="Run the Campus Customs agent team")
    ap.add_argument("--ticket", type=int, action="append", help="ticket id (repeatable)")
    ap.add_argument("--all", action="store_true", help="every open ticket on the board")
    ap.add_argument("--reset", action="store_true", help="reset the working DB from the original first")
    args = ap.parse_args()

    if args.reset:
        reset_working_db()
    ids = list(args.ticket or [])
    if args.all:
        ids += [t for t in await open_ticket_ids() if t not in ids]
    if not ids:
        ap.error("pass --ticket N or --all")

    for ticket_id in ids:  # one ticket at a time keeps spend and the audit trail easy to follow
        result = await run_ticket(ticket_id)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
