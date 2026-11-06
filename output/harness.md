# Campus Customs Multi-Agent Operations — Harness

## Database

- Original: `data/campus_customs.db` (read-only, used only to reset)
- Working copy: `data/campus_customs_new.db` (what the MCP server and backend use)
- Shop "today" = `desk.date_today` = 2026-08-31
- Reset before a full run: copy the original over the working copy (`POST /api/reset`, the **Reset shop** button, or `python -m backend.run_team --reset`)

### Tables

| Table | What it holds | Read by (MCP tool) | Written by (MCP tool) |
|---|---|---|---|
| `desk` | the shop's "today" (`date_today`), which decides what's overdue | almost every tool (`today`) | — |
| `tickets` | the board: type, requester, SKU/size/qty, linked lease or invoice, status, notes | `list_tickets`, `list_open_tickets`, `get_ticket` | `update_ticket_status` (status + dated note) |
| `inventory` | qty on hand and shelf location per SKU + size | `check_stock`, `prepare_purchase_order`, `purchase_with_approval` | — (goods arrive later; not modeled) |
| `pricing` | unit cost and list price per SKU | `get_price_and_margin`, `prepare_purchase_order`, `purchase_with_approval` | — |
| `vendors` | who makes what and their lead time in days | `list_vendors`, `list_invoices`, `prepare_*`, `*_with_approval` | — |
| `invoices` | money we owe vendors (amount, due date, open/paid) | `list_vendors`, `list_invoices`, `prepare_payment`, `prepare_purchase_order` | `pay_with_approval` (marks paid), `purchase_with_approval` (adds a paid row for the order) |
| `leases` | the shop space: rent and next due date | `get_rent_status`, `prepare_payment` | `pay_with_approval` (moves `next_due` a month) |
| `cash_accounts` | checking balance (cash only goes out) | `get_rent_status`, `get_cash_balances`, `prepare_*` | `pay_with_approval`, `purchase_with_approval` (lower the balance; never below 0) |
| `payments` | every payment made, with `approved_by` | — | `pay_with_approval`, `purchase_with_approval` (one row each) |

## MCP tools

Server: `mcp_server/server.py` (FastMCP), 14 tools. None of them makes up values: if a SKU, size, lease, invoice or ticket isn't on file, the tool says so instead of guessing. The first three below (Problem 3) only read the database. The tools added in Problems 5 and 7 are in the table after them; three of them write.

### 1. `check_stock(sku, size, qty_needed)`

- **Tables it reads:** `inventory` (the row for one `sku` + `size`)
- **Tickets it unlocks:** **101** (Tauhid Zaman wants 1 `CC-TEE-WHITE` in S) and **103** (Yale AI Club wants 20 `CC-HOOD-NAVY` in M)
- **Why it's the right tool:** Both tickets give an exact SKU, size and quantity, and the first thing to settle is whether we can fill them off the shelf. For 101 it returns 0 on hand (short 1, so the tee needs a restock), and for 103 it returns 8 on hand (short 12, so we can't fill 20 even before talking about price).

### 2. `get_rent_status(lease_id)`

- **Tables it reads:** `leases` (the lease row), `desk` (today's date) and `cash_accounts` (balances)
- **Ticket it unlocks:** **102** (Elm City Properties rent notice, `lease_id = 1`)
- **Why it's the right tool:** The rent ticket comes down to how much is owed, whether it's overdue, and whether we can afford it. For lease 1 it returns $2,400 due 2026-09-02, 2 days after today (not overdue), with $3,400 in checking, so it can be covered and leaves $1,000. Payment still needs human approval.

### 3. `get_price_and_margin(sku)`

- **Tables it reads:** `pricing` (unit cost and list price for one SKU)
- **Ticket it unlocks:** **103** (Yale AI Club bulk discount on `CC-HOOD-NAVY`)
- **Why it's the right tool:** A discount request can't be judged without knowing what the hoodie costs us. It returns a $22 cost against a $58 list price: $36 margin per hoodie, so any discount under 62.1% still doesn't lose money.

### Tools added in Problem 5

The first three tools didn't read `invoices`, `vendors` or `payments`, and nothing could write. Ticket 101 hangs on invoice #501 ($840 to Bulldog Print Co, overdue since 2026-08-28), which blocks a tee restock, so the team needed more tools. All shop facts still come through this one MCP server; the backend never opens the database itself.

| Tool | Tables it uses | Reads / writes | Ticket | Which agents get it |
|---|---|---|---|---|
| `list_open_tickets()` | `tickets` | read | all | Boss |
| `get_ticket(ticket_id)` | `tickets` | read | all | everyone |
| `list_vendors()` | `vendors`, `invoices`, `desk` | read | 101, 103 (restock) | Inventory, Accounting |
| `list_invoices(status)` | `invoices`, `vendors`, `desk` | read | 101 (invoice 501) | Accounting |
| `get_cash_balances()` | `cash_accounts`, `desk` | read | 101, 102 | Accounting, Facilities |
| `prepare_payment(kind, ref_id, account)` | `invoices` or `leases`, `vendors`, `cash_accounts`, `desk` | read only: builds an approval request, pays nothing | 101 (invoice), 102 (rent) | Accounting, Facilities |
| `prepare_purchase_order(vendor_id, sku, size, qty)` | `vendors`, `invoices`, `pricing`, `inventory`, `cash_accounts`, `desk` | read only: builds an approval request, orders nothing | 101, 103 | Inventory, Accounting |
| `update_ticket_status(ticket_id, status, note)` | `tickets`, `desk` | **writes** `tickets.status` and appends a dated note (keeps the original notes) | all | Boss |
| `pay_with_approval(kind, ref_id, approved_by, account)` | `payments`, `cash_accounts`, `invoices` or `leases`, `vendors`, `desk` | **writes**: adds a `payments` row, lowers the cash balance, marks the invoice paid or moves the lease's `next_due` on a month. Refuses with no human approver, an already-paid invoice, or a balance that would go negative | 101, 102 | **No agent.** Only the backend's approve routes call it |
| `list_tickets()` *(added in Problem 7)* | `tickets` | read: every ticket, resolved or not | all | No agent; the backend's ticket list |
| `purchase_with_approval(vendor_id, sku, size, qty, approved_by, account)` *(added in Problem 7)* | `invoices`, `payments`, `cash_accounts`, `vendors`, `pricing`, `inventory`, `desk` | **writes**: pays for a restock up front (unit cost × qty). It records the order as a paid `invoices` row (SKU, size, qty, arrival date) plus a `payments` row and lowers the cash balance. Refuses while the vendor has an unpaid invoice, without a human approver, or if cash would go negative | 101, 103 | **No agent.** Only the backend's approve routes call it |

On a scratch copy: invoice 501 prepares as $840 (overdue 3 days, $2,560 left). Rent prepares as $2,400 (due in 2 days, $1,000 left). A tee S restock from Bulldog Print Co is $8 with arrival 2026-09-05, but it's blocked until 501 is paid. Paying both leaves $160, and a third payment is refused.

## Agents

Built with PydanticAI in `backend/`. Every agent uses `gpt-6-luna` through Portkey (`PORTKEY_API_KEY`); the model name is fixed in `backend/config.py` with no override. Prompts are in `backend/prompts/` (one file per agent), and data types are in `backend/models.py`.

| Agent | Prompt | What it does | MCP tools | Returns |
|---|---|---|---|---|
| Boss | `prompts/boss.md` | Reads the ticket, decides who works on it, collects reports, makes the final call, moves the ticket on the board | `list_open_tickets`, `get_ticket`, `update_ticket_status` | `TicketDecision` |
| Inventory | `prompts/inventory.md` | Stock by SKU and size, shortfalls, which vendor can restock, when it would arrive, and whether an unpaid invoice blocks it | `get_ticket`, `check_stock`, `list_vendors`, `prepare_purchase_order` | `AgentReport` |
| Accounting | `prompts/accounting.md` | Cash, invoices, margins and discounts. Prepares payments and purchase orders for human approval | `get_ticket`, `get_price_and_margin`, `list_invoices`, `list_vendors`, `get_cash_balances`, `prepare_payment`, `prepare_purchase_order` | `AgentReport` |
| Facilities | `prompts/facilities.md` | Lease, rent amount and due date, whether cash covers it. Prepares the rent payment for approval | `get_ticket`, `get_rent_status`, `get_cash_balances`, `prepare_payment` | `AgentReport` |
| Customer Service | `prompts/customer_service.md` | Drafts replies to requesters. Drafts stay on the board; nothing is sent | `get_ticket`, `check_stock`, `get_price_and_margin` | `AgentReport` (with `customer_draft`) |

**Full connectivity:** every agent also has `delegate(to, task)`, so any agent can hand work to any other. Specialists can call each other too (for example, Inventory asks Accounting about the invoice blocking a restock). The teammate runs its own agent loop and hands back a structured `AgentReport`.

**Agent loop** (`backend/team.py`, `run_agent`): model call → MCP tool calls and/or delegations → model call … → structured output. The Boss starts each ticket with `run_ticket(ticket_id)`. Run from `hw5/` with `.venv/bin/python -m backend.run_team --ticket 101` or `--all --reset`.

**Audit trail:** every step is appended to `output/audit_trail.json`, never wiped. Each entry records the time, run id, ticket, agent, delegation chain (e.g. `boss → inventory`), step number, and event type:
- `run_start`: the task, prompt file and its hash, and allowed tools
- `model_request`: the prompt, tool results or retries sent
- `model_response`: tool calls with arguments, text, tokens, and the model name the API reports. Every request asks for `gpt-6-luna`; in the live run Portkey reported it back as `gpt-6-luna-global`, its deployment label for the same model.
- `delegation_start`, `delegation_end` or `delegation_refused`
- `final_output`, `run_end` or `error`

Each entry also carries team-wide usage so far. Long tool results are cut to 2,000 characters in the file only, never for the agent.

## Backend routes

`backend/main.py` (FastAPI). Start it from `backend/` with `uvicorn main:app --reload --port 8000` (hw5 venv active) → `http://localhost:8000`. Every shop read and write goes through the MCP server.

- `GET /api/health` — is the backend up, the model (`gpt-6-luna`), whether a Portkey key is set, and any run in progress.
- `GET /api/tickets` — every ticket with `state` = `open` or `resolved` (plus its finer board `status`).
- `GET /api/tickets/{id}` — one ticket.
- `POST /api/tickets/{id}/run` — run the agent team on that ticket. Returns a `run_id` right away (`?wait=true` waits for the result). One run at a time.
- `GET /api/runs/{run_id}` — whether that run is still going, plus its result: the Boss's decision, approvals, draft and token usage.
- `GET /api/events?since=&ticket_id=&run_id=&limit=` — recent agent events from the audit trail: which agent, what it said, which tools it called with which arguments, and what came back. Poll with `since=next_since` to get only new events.
- `GET /api/tickets/{id}/summary` — what each agent did on that ticket's latest run: who asked it, MCP tools used (with counts), hand-offs, its final answer and tokens. Agents that weren't called are marked as not used. *(added in Problem 8 for the dashboard)*
- `GET /api/approvals?ticket_id=&status=` — the payments, purchases and discounts the agents prepared for a person, each marked pending or approved.
- `POST /api/approvals/{approval_id}/approve` (body `{"approved_by": "<name>"}`) — a human approves one of those. **This is where cash changes:** a payment or purchase runs the human-only MCP tool, with amounts re-read from the database. A discount is just recorded.
- `POST /api/approve` (body with `type`, the IDs and `approved_by`) — a human approves a payment (`invoice`/`rent` + `ref_id`) or a purchase (`vendor_id`, `sku`, `size`, `qty`) typed in directly. Same tools, same refusals.
- `GET /api/cash` — current checking balance from `cash_accounts`.
- `POST /api/reset` — copy the original `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run (refused while a run is going). The audit trail is kept, and the reset is logged in it.

## Dashboard

`frontend/` (React + Vite + TypeScript). Run `npm run dev` there → `http://localhost:5173`. It calls the backend at `http://localhost:8000`; the backend's CORS allows the Vite origin. The design choices are in `output/design.md`.

- **Board:** the three tickets as order slips, with open / agents on it / resolved (green RESOLVED stamp) and how many items wait for a signature.
- **Run the team:** pick a slip, press **Run the team** (`POST /api/tickets/{id}/run`). One run at a time.
- **The floor:** the five agents as stations with live status and a speech bubble (what each one says, the tool it's calling). Hand-off lines light up as one agent delegates to another, and agents not called show "sat this one out". It's fed by polling `GET /api/events`.
- **Who did what:** a card per agent from `GET /api/tickets/{id}/summary`.
- **Needs your signature:** approval chits from `GET /api/approvals`. The person types their name and approves (`POST /api/approvals/{id}/approve`). Payments and purchases move cash only here, and refusals (vendor blocked, not enough cash) show on the chit.
- **Cash register:** checking from `GET /api/cash`. It rolls down and shows the amount that left after an approved payment.
- **Floor radio:** every step of the run, in order.
- **Reset shop:** `POST /api/reset`, after a confirm.

## Safety

Guardrails a real business would want once agents touch real customers and real money:

- **People approve money.** No agent can pay. The two money tools (`pay_with_approval`, `purchase_with_approval`) aren't in any agent's tool list and are only called by the backend's approve routes. They need a named human approver (agent names are rejected) and re-read the amount from the database. Each approval or refusal is logged as a `human_approval` event. Agents can only *prepare* payments, purchase orders and discounts as approval requests.
- **No negative balances.** The pay tool refuses if the account can't cover the payment, and it runs in one database transaction, so a failure changes nothing.
- **Nothing leaves the shop.** No email or vendor tools exist. Customer messages are drafts on the board until a person sends them.
- **Least privilege.** Each agent sees only the MCP tools its role needs. Only the Boss can change a ticket's status, and every change appends a dated note instead of overwriting.
- **No made-up facts.** Every number comes from an MCP tool. Tools error out on unknown SKUs, sizes, leases, invoices or tickets instead of guessing, and prompts tell agents to report "unknown".
- **Original data is safe.** Agents only work on `campus_customs_new.db`. `--reset` copies the read-only original over it, and refuses if the paths are the same.
- **Audit everything.** The append-only audit trail lets someone replay who decided what, with which tool output, and what it cost.
- **For real customers I'd add:** a spending cap per payment and per day, two-person approval above a threshold, approval links that expire, and a review queue for any discount above a set percentage.

Limits that keep token use in check (`backend/config.py`):

- **One shared budget per ticket.** Delegated runs add to the Boss's usage, and `UsageLimits` stops the whole team at 40 model calls, 60 tool calls or 250,000 tokens.
- **At most 6,000 output tokens** per model response.
- **Delegation limits.** At most 8 hand-offs per ticket and a chain at most 3 deep. No delegating to yourself or to anyone already waiting in the chain, which stops ping-pong loops.
- **Tool retries capped** at 2 per MCP tool and 2 output retries per agent.
- **Short prompts and reports.** Prompts tell agents to ask one specific question per teammate, never repeat a tool call, and keep reports short. Structured reports pass between agents instead of whole conversations.
- **One ticket at a time** from the CLI, so a bad ticket can't fan out across the whole board.

## Full run (Problem 9)

Reset the working database, then ran 101, 102 and 103 one at a time from the dashboard on `gpt-6-luna`. All three resolved. A person (Eric) signed the approvals in the sign-off tray.

| Ticket | Run | Agents that worked | Model calls | Tokens | Cash |
|---|---|---|---|---|---|
| 101 tee | `24775a4f0449` | Boss, Inventory, Accounting, Customer Service | 16 | 34,259 | −$848 (invoice 501 $840 + 1 tee $8) |
| 102 rent | `e31140e1f1d1` | Boss, Facilities, Accounting | 17 | 36,273 | −$2,400 (rent) |
| 103 hoodies | `8d07f9ea9496` | Boss, Inventory, Accounting, Customer Service | 19 | 46,135 | $0 (duplicate 501 refused as already paid; $264 restock refused because checking only had $152) |

Checking went from $3,400 to $152, which matches `cash_accounts`. Evidence: `output/desk_tickets.html` (Expected vs Actual, Cash, Reflection), `output/resolved_tickets.json`, `output/resolved_board.html`, and `output/audit_trail.json` (the reset, every agent step and every human approval, appended).

