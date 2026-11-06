# Campus Customs MCP server

A FastMCP server that gives the Campus Customs agent team its tools. Agents call these tools to look things up in the shop database instead of guessing, so every answer about stock, rent or prices comes from real rows.

## Database

It uses the working copy `data/campus_customs_new.db` (the path is relative to the `hw5/` folder). It never touches the original `data/campus_customs.db`, which is kept to reset the working copy. Set `CAMPUS_CUSTOMS_DB` to point it at a different file, for example a scratch copy for testing.

Eleven of the 14 tools open the database read-only. Three write: `update_ticket_status`, `pay_with_approval` and `purchase_with_approval`. Each runs as one transaction, so a refusal or error changes nothing.

## Tools

| Tool | What it does | Tables | Ticket |
|---|---|---|---|
| `check_stock(sku, size, qty_needed)` | On-hand count and shelf location for a SKU and size, plus the shortfall if you pass how many are needed | `inventory` | 101, 103 |
| `get_rent_status(lease_id)` | Rent amount, due date and days until due (from `desk.date_today`), and whether each cash account can cover it | `leases`, `desk`, `cash_accounts` | 102 |
| `get_price_and_margin(sku)` | Unit cost, list price, margin per unit, and the largest discount that still doesn't sell below cost | `pricing` | 103 |
| `list_open_tickets()` | Every ticket that isn't resolved, oldest first | `tickets` | all |
| `get_ticket(ticket_id)` | One ticket with its linked SKU, size, qty, lease or invoice | `tickets` | all |
| `list_vendors()` | Each vendor's specialty, lead time, earliest arrival if ordered today, unpaid invoices, and `can_ship` (false while an invoice is unpaid) | `vendors`, `invoices`, `desk` | 101, 103 |
| `list_invoices(status="open")` | Vendor invoices with days overdue as of `desk.date_today` | `invoices`, `vendors`, `desk` | 101 |
| `get_cash_balances()` | Balance of each cash account | `cash_accounts`, `desk` | 101, 102 |
| `prepare_payment(kind, ref_id, account="checking")` | Builds a payment for human approval (`invoice` or `rent`): amount from the database, balance before and after, whether the account can cover it. Pays nothing | `invoices` or `leases`, `vendors`, `cash_accounts`, `desk` | 101, 102 |
| `prepare_purchase_order(vendor_id, sku, size, qty)` | Builds a restock order for human approval: unit cost, total, arrival date, and whether the vendor is blocked by an unpaid invoice. Orders nothing | `vendors`, `invoices`, `pricing`, `inventory`, `cash_accounts`, `desk` | 101, 103 |
| `update_ticket_status(ticket_id, status, note)` | **Writes.** Moves a ticket to `open`, `in_progress`, `waiting_on_human` or `resolved` and appends a dated note (the original notes stay) | `tickets`, `desk` | all |
| `pay_with_approval(kind, ref_id, approved_by, account="checking")` | **Writes, human-approved only.** Adds a `payments` row, lowers the balance, and marks the invoice paid or moves the lease's `next_due` on a month. Refuses without a named human approver (agent names are rejected), for an already-paid invoice, or if the balance would go negative. The backend gives this tool to no agent | `payments`, `cash_accounts`, `invoices` or `leases`, `vendors`, `desk` | 101, 102 |
| `list_tickets()` | Every ticket, resolved or not, with `resolved` true/false (for the dashboard) | `tickets` | all |
| `purchase_with_approval(vendor_id, sku, size, qty, approved_by, account="checking")` | **Writes, human-approved only.** Pays for a restock up front (`pricing.unit_cost` × qty). It records the order as a paid `invoices` row (SKU, size, qty, arrival date) plus a `payments` row and lowers the balance. Inventory goes up when the order arrives. Refuses while the vendor has an unpaid invoice, without a named human approver, or if the balance would go negative. The backend gives this tool to no agent | `invoices`, `payments`, `cash_accounts`, `vendors`, `pricing`, `inventory`, `desk` | 101, 103 |

If a SKU, size, lease, invoice, ticket, vendor or account isn't in the database, the tool returns an error saying so.

The agent team in `backend/` connects to this server over stdio and gives each agent only the tools its role needs (`backend/shop_mcp.py`).

## Run it

```bash
cd hw5
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r mcp_server/requirements.txt
.venv/bin/python mcp_server/server.py
```

It runs over stdio, so an MCP client (the backend, Claude Code, etc.) starts it as a subprocess.

## Connect it to a vibe coder

The connection is saved in `hw5/.mcp.json` as the server `campus-customs`. Paths are relative to `hw5/`, so open the vibe coder in the `hw5/` folder:

```json
{
  "mcpServers": {
    "campus-customs": {
      "type": "stdio",
      "command": ".venv/bin/python",
      "args": ["mcp_server/server.py"]
    }
  }
}
```

Claude Code reads `.mcp.json` when it starts and asks once to approve the project's servers.

## Smoke test

```bash
.venv/bin/python mcp_server/smoke_test.py
```

Starts the server from `.mcp.json`, calls each tool for its ticket (101, 102, 103) plus three inputs that aren't in the database, checks every answer against direct SQL, and confirms the database file didn't change. Evidence goes to `output/mcp_smoke.json`.
