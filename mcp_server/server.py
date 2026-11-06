"""Campus Customs MCP server.

Talks only to the working copy data/campus_customs_new.db (never the original).
Every value a tool returns comes from the database or is arithmetic on database
values. If something isn't in the database, the tool says so instead of guessing.
"""

import os
import sqlite3
from datetime import date
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

HW5_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("CAMPUS_CUSTOMS_DB", HW5_DIR / "data" / "campus_customs_new.db"))

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Tools for the Campus Customs shop. All answers come from the shop database. "
        "'Today' is desk.date_today, not the real calendar date."
    ),
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise ToolError(f"Database not found at {DB_PATH}")
    # These tools only read, so open read-only.
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _today(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT date_today FROM desk").fetchone()
    if row is None:
        raise ToolError("desk table has no date_today")
    return row["date_today"]


@mcp.tool
def check_stock(sku: str, size: str, qty_needed: int | None = None) -> dict:
    """Look up how many of a SKU in a given size are on the shelf (inventory table).

    Pass qty_needed to get the shortfall, e.g. a customer wants 20 and we have 8.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, name, size, qty, location FROM inventory WHERE sku = ? AND size = ?",
            (sku, size),
        ).fetchone()
        if row is None:
            sizes = [r["size"] for r in conn.execute("SELECT size FROM inventory WHERE sku = ?", (sku,))]
            if not sizes:
                raise ToolError(f"SKU {sku} is not in inventory")
            raise ToolError(f"SKU {sku} has no size {size}; sizes on file: {', '.join(sizes)}")

    result = {
        "sku": row["sku"],
        "name": row["name"],
        "size": row["size"],
        "qty_on_hand": row["qty"],
        "location": row["location"],
    }
    if qty_needed is not None:
        result["qty_needed"] = qty_needed
        result["shortfall"] = max(qty_needed - row["qty"], 0)
        result["can_fill_from_stock"] = row["qty"] >= qty_needed
    return result


@mcp.tool
def get_rent_status(lease_id: int) -> dict:
    """Check a lease's rent: amount, due date vs. the shop's today (desk table),
    and whether the cash accounts can cover it (leases + cash_accounts tables)."""
    with _connect() as conn:
        today = _today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            raise ToolError(f"Lease {lease_id} is not in the leases table")
        accounts = conn.execute("SELECT name, balance, date FROM cash_accounts").fetchall()

    days_until_due = (date.fromisoformat(lease["next_due"]) - date.fromisoformat(today)).days
    return {
        "today": today,
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": lease["monthly_rent"],
        "next_due": lease["next_due"],
        "days_until_due": days_until_due,
        "overdue": days_until_due < 0,
        "notes": lease["notes"],
        "cash_accounts": [
            {
                "account": a["name"],
                "balance": a["balance"],
                "as_of": a["date"],
                "can_cover_rent": a["balance"] >= lease["monthly_rent"],
                "balance_after_rent": a["balance"] - lease["monthly_rent"],
            }
            for a in accounts
        ],
    }


@mcp.tool
def get_price_and_margin(sku: str) -> dict:
    """Look up a SKU's unit cost and list price (pricing table) and the margin,
    so a discount request can be checked against what the shirt or hoodie costs us."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT sku, unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if row is None:
        raise ToolError(f"SKU {sku} is not in the pricing table")

    margin = row["list_price"] - row["unit_cost"]
    return {
        "sku": row["sku"],
        "unit_cost": row["unit_cost"],
        "list_price": row["list_price"],
        "margin_per_unit": margin,
        # Margin as a % of list price = the biggest discount that still doesn't sell below cost.
        "max_discount_pct_before_loss": round(100 * margin / row["list_price"], 1),
    }


# ---------------------------------------------------------------------------
# Tools added in Problem 5 so the agent team can work the open tickets.
# ---------------------------------------------------------------------------

TICKET_STATUSES = ("open", "in_progress", "waiting_on_human", "resolved")
PAYMENT_KINDS = ("invoice", "rent")
# Agent names can never sign off on a payment; only a person can.
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer service", "customer_service", "agent"}


def _connect_rw() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise ToolError(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, isolation_level=None)  # we run BEGIN/COMMIT ourselves
    conn.row_factory = sqlite3.Row
    return conn


def _ticket_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end[:10]) - date.fromisoformat(start[:10])).days


def _add_days(day: str, n: int) -> str:
    return date.fromordinal(date.fromisoformat(day).toordinal() + n).isoformat()


def _add_one_month(day: str) -> str:
    d = date.fromisoformat(day)
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    for dd in (d.day, 30, 29, 28):  # clamp, e.g. Jan 31 -> Feb 28
        try:
            return date(year, month, dd).isoformat()
        except ValueError:
            continue
    raise ToolError(f"Could not add a month to {day}")


def _open_invoices_by_vendor(conn: sqlite3.Connection) -> dict[int, list[sqlite3.Row]]:
    out: dict[int, list[sqlite3.Row]] = {}
    for inv in conn.execute("SELECT * FROM invoices WHERE status != 'paid' ORDER BY due_date"):
        out.setdefault(inv["vendor_id"], []).append(inv)
    return out


def _payment_target(conn: sqlite3.Connection, kind: str, ref_id: int) -> dict:
    """Amount and payee for an invoice or a lease's rent, straight from the database."""
    if kind == "invoice":
        inv = conn.execute(
            "SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id WHERE i.id = ?",
            (ref_id,),
        ).fetchone()
        if inv is None:
            raise ToolError(f"Invoice {ref_id} is not in the invoices table")
        return {"kind": "invoice", "ref_id": inv["id"], "payee": inv["vendor_name"], "amount": inv["amount"],
                "due_date": inv["due_date"], "status": inv["status"], "description": inv["description"],
                "already_paid": inv["status"] == "paid"}
    if kind == "rent":
        lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
        if lease is None:
            raise ToolError(f"Lease {ref_id} is not in the leases table")
        return {"kind": "rent", "ref_id": lease["id"], "payee": lease["landlord"], "amount": lease["monthly_rent"],
                "due_date": lease["next_due"], "status": "due", "description": f"Rent for {lease['space_name']}",
                "already_paid": False}
    raise ToolError(f"kind must be one of {', '.join(PAYMENT_KINDS)}, not {kind!r}")


@mcp.tool
def list_open_tickets() -> list[dict]:
    """List every ticket on the board that is not resolved yet (tickets table), oldest first."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tickets WHERE status != 'resolved' ORDER BY created_at").fetchall()
    return [_ticket_dict(r) for r in rows]


@mcp.tool
def list_tickets() -> list[dict]:
    """Every ticket on the board (tickets table), resolved or not, with resolved true/false."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    return [{**_ticket_dict(r), "resolved": r["status"] == "resolved"} for r in rows]


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Read one ticket (tickets table): who asked, what for, and any linked SKU, size, qty, lease or invoice."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise ToolError(f"Ticket {ticket_id} is not in the tickets table")
    return _ticket_dict(row)


@mcp.tool
def list_vendors() -> dict:
    """List vendors (vendors table) with what they make, lead time, earliest arrival if ordered
    today (desk.date_today), and any unpaid invoices (invoices table). A vendor with an unpaid
    invoice will not ship new product, so can_ship is false until it is paid."""
    with _connect() as conn:
        today = _today(conn)
        open_by_vendor = _open_invoices_by_vendor(conn)
        vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
    out = []
    for v in vendors:
        unpaid = open_by_vendor.get(v["id"], [])
        out.append({
            "vendor_id": v["id"],
            "name": v["name"],
            "specialty": v["specialty"],
            "lead_days": v["lead_days"],
            "earliest_arrival_if_ordered_today": _add_days(today, v["lead_days"]),
            "unpaid_invoices": [
                {"invoice_id": i["id"], "amount": i["amount"], "due_date": i["due_date"],
                 "days_overdue": max(_days_between(i["due_date"], today), 0)}
                for i in unpaid
            ],
            "can_ship": not unpaid,
        })
    return {"today": today, "vendors": out}


@mcp.tool
def list_invoices(status: str | None = "open") -> dict:
    """List vendor invoices (invoices + vendors tables) with how many days overdue each is as of
    desk.date_today. status='open' (default) shows unpaid ones; pass None for all."""
    with _connect() as conn:
        today = _today(conn)
        sql = ("SELECT i.*, v.name AS vendor_name FROM invoices i JOIN vendors v ON v.id = i.vendor_id")
        rows = conn.execute(sql + (" WHERE i.status = ?" if status else "") + " ORDER BY i.due_date",
                            (status,) if status else ()).fetchall()
    return {
        "today": today,
        "invoices": [
            {"invoice_id": r["id"], "vendor_id": r["vendor_id"], "vendor_name": r["vendor_name"],
             "amount": r["amount"], "due_date": r["due_date"], "status": r["status"],
             "description": r["description"],
             "days_overdue": max(_days_between(r["due_date"], today), 0) if r["status"] != "paid" else 0,
             "overdue": r["status"] != "paid" and r["due_date"] < today}
            for r in rows
        ],
    }


@mcp.tool
def get_cash_balances() -> dict:
    """Cash on hand in each account (cash_accounts table). Cash only goes out; there is no revenue."""
    with _connect() as conn:
        today = _today(conn)
        rows = conn.execute("SELECT name, balance, date FROM cash_accounts ORDER BY name").fetchall()
    return {"today": today, "accounts": [{"account": r["name"], "balance": r["balance"], "as_of": r["date"]} for r in rows]}


@mcp.tool
def prepare_payment(kind: str, ref_id: int, account: str = "checking") -> dict:
    """Prepare (but do NOT make) a payment for human approval. kind is 'invoice' (ref_id =
    invoices.id) or 'rent' (ref_id = leases.id). The amount always comes from the database, and
    the result says whether the account can cover it. Nothing is written; a person must approve."""
    with _connect() as conn:
        today = _today(conn)
        target = _payment_target(conn, kind, ref_id)
        acct = conn.execute("SELECT name, balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if acct is None:
        raise ToolError(f"Cash account {account!r} is not in the cash_accounts table")
    can_cover = acct["balance"] >= target["amount"]
    return {
        **target,
        "today": today,
        "days_until_due": _days_between(today, target["due_date"]),
        "account": account,
        "balance_now": acct["balance"],
        "balance_after": acct["balance"] - target["amount"],
        "can_cover": can_cover,
        "needs_human_approval": True,
        "ready_for_approval": can_cover and not target["already_paid"],
    }


@mcp.tool
def prepare_purchase_order(vendor_id: int, sku: str, size: str, qty: int) -> dict:
    """Prepare (but do NOT place) a restock purchase order for human approval. Cost comes from
    pricing.unit_cost, lead time from vendors, and the vendor is blocked while it has an unpaid
    invoice (invoices). Also checks cash (cash_accounts) and today's date (desk). Nothing is written."""
    if qty <= 0:
        raise ToolError("qty must be at least 1")
    with _connect() as conn:
        today = _today(conn)
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            raise ToolError(f"Vendor {vendor_id} is not in the vendors table")
        item = conn.execute("SELECT name FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if item is None:
            raise ToolError(f"SKU {sku} in size {size} is not in inventory")
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            raise ToolError(f"SKU {sku} is not in the pricing table")
        unpaid = _open_invoices_by_vendor(conn).get(vendor_id, [])
        checking = conn.execute("SELECT balance FROM cash_accounts WHERE name = 'checking'").fetchone()
    total = price["unit_cost"] * qty
    return {
        "today": today,
        "vendor_id": vendor["id"],
        "vendor_name": vendor["name"],
        "vendor_specialty": vendor["specialty"],
        "sku": sku,
        "item_name": item["name"],
        "size": size,
        "qty": qty,
        "unit_cost": price["unit_cost"],
        "total_cost": total,
        "lead_days": vendor["lead_days"],
        "earliest_arrival": _add_days(today, vendor["lead_days"]),
        "blocked_by_unpaid_invoices": [{"invoice_id": i["id"], "amount": i["amount"], "due_date": i["due_date"]} for i in unpaid],
        "vendor_will_ship": not unpaid,
        "checking_balance": checking["balance"] if checking else None,
        "needs_human_approval": True,
    }


@mcp.tool
def update_ticket_status(ticket_id: int, status: str, note: str) -> dict:
    """Move a ticket on the board (tickets table) to open, in_progress, waiting_on_human or
    resolved, and append a dated note saying why. The original notes are kept."""
    if status not in TICKET_STATUSES:
        raise ToolError(f"status must be one of {', '.join(TICKET_STATUSES)}")
    if not note.strip():
        raise ToolError("note is required so the board shows why the status changed")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        today = _today(conn)
        row = conn.execute("SELECT status, notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            raise ToolError(f"Ticket {ticket_id} is not in the tickets table")
        notes = (row["notes"] or "").rstrip()
        notes = f"{notes}\n[{today}] {status}: {note.strip()}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"ticket_id": ticket_id, "old_status": row["status"], "new_status": status, "notes": notes}


@mcp.tool
def pay_with_approval(kind: str, ref_id: int, approved_by: str, account: str = "checking") -> dict:
    """HUMAN-APPROVED PAYMENTS ONLY. Pays an invoice ('invoice', invoices.id) or a lease's rent
    ('rent', leases.id) after a named person approved it. Refuses if the account can't cover it
    (no negative balances), if the invoice is already paid, or if approved_by is not a person.
    Writes payments, lowers cash_accounts, and marks the invoice paid or moves the lease's
    next_due on by one month. The backend never gives this tool to an agent."""
    approver = (approved_by or "").strip()
    if not approver or approver.lower() in AGENT_NAMES:
        raise ToolError("A payment needs a named human approver; agents cannot approve payments")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        today = _today(conn)
        target = _payment_target(conn, kind, ref_id)
        if target["already_paid"]:
            raise ToolError(f"Invoice {ref_id} is already paid")
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            raise ToolError(f"Cash account {account!r} is not in the cash_accounts table")
        if acct["balance"] < target["amount"]:
            raise ToolError(
                f"Refused: {account} has {acct['balance']:.2f}, payment is {target['amount']:.2f}; "
                "balances can't go negative"
            )
        new_balance = acct["balance"] - target["amount"]
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today, account))
        cur = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?, ?, ?, ?, ?, ?)",
            (kind, ref_id, target["amount"], account, today, approver),
        )
        if kind == "invoice":
            conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (ref_id,))
            follow_up = {"invoice_status": "paid"}
        else:
            next_due = _add_one_month(target["due_date"])
            conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (next_due, ref_id))
            follow_up = {"lease_next_due": next_due}
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"payment_id": cur.lastrowid, "kind": kind, "ref_id": ref_id, "payee": target["payee"],
            "amount": target["amount"], "account": account, "balance_after": new_balance,
            "paid_at": today, "approved_by": approver, **follow_up}


@mcp.tool
def purchase_with_approval(vendor_id: int, sku: str, size: str, qty: int, approved_by: str,
                           account: str = "checking") -> dict:
    """HUMAN-APPROVED PURCHASES ONLY. Buys a restock from a vendor and pays for it up front
    after a named person approved it. Cost = pricing.unit_cost x qty. Refuses if the vendor
    still has an unpaid invoice (they won't ship), if the account can't cover it, or if
    approved_by is not a person. Records the order as a paid row in invoices (with the SKU,
    size, qty and arrival date) plus a payments row, and lowers cash_accounts. Inventory goes
    up when the order arrives, not now. The backend never gives this tool to an agent."""
    approver = (approved_by or "").strip()
    if not approver or approver.lower() in AGENT_NAMES:
        raise ToolError("A purchase needs a named human approver; agents cannot approve purchases")
    if qty <= 0:
        raise ToolError("qty must be at least 1")
    conn = _connect_rw()
    try:
        conn.execute("BEGIN IMMEDIATE")
        today = _today(conn)
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            raise ToolError(f"Vendor {vendor_id} is not in the vendors table")
        item = conn.execute("SELECT name FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        if item is None:
            raise ToolError(f"SKU {sku} in size {size} is not in inventory")
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            raise ToolError(f"SKU {sku} is not in the pricing table")
        unpaid = _open_invoices_by_vendor(conn).get(vendor_id, [])
        if unpaid:
            ids = ", ".join(str(i["id"]) for i in unpaid)
            raise ToolError(f"Refused: {vendor['name']} won't ship while invoice {ids} is unpaid")
        acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
        if acct is None:
            raise ToolError(f"Cash account {account!r} is not in the cash_accounts table")
        total = price["unit_cost"] * qty
        if acct["balance"] < total:
            raise ToolError(
                f"Refused: {account} has {acct['balance']:.2f}, purchase is {total:.2f}; balances can't go negative"
            )
        arrival = _add_days(today, vendor["lead_days"])
        description = f"Purchase order: {qty} x {sku} {size} ({item['name']}), arrives {arrival}, approved by {approver}"
        inv = conn.execute(
            "INSERT INTO invoices (vendor_id, amount, due_date, status, description) VALUES (?, ?, ?, 'paid', ?)",
            (vendor_id, total, today, description),
        )
        pay = conn.execute(
            "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES ('purchase_order', ?, ?, ?, ?, ?)",
            (inv.lastrowid, total, account, today, approver),
        )
        new_balance = acct["balance"] - total
        conn.execute("UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?", (new_balance, today, account))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"payment_id": pay.lastrowid, "invoice_id": inv.lastrowid, "vendor": vendor["name"], "sku": sku,
            "size": size, "qty": qty, "unit_cost": price["unit_cost"], "amount": total, "account": account,
            "balance_after": new_balance, "paid_at": today, "arrives": arrival, "approved_by": approver}


if __name__ == "__main__":
    mcp.run(show_banner=False)
