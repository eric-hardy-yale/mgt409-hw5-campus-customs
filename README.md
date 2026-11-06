# Campus Customs Multi-Agent Operations (MGT 409, HW5)

A five-agent team (Boss, Inventory, Accounting, Facilities, Customer Service) that works the open tickets of a small campus print shop. It has three pieces that talk to each other:

- **MCP server** (`mcp_server/`, FastMCP): the only way anything reads or writes the shop database.
- **FastAPI backend** (`backend/`): the PydanticAI agent team plus the routes the dashboard calls.
- **React dashboard** (`frontend/`, Vite + TypeScript): pick a ticket, watch the agents work, and sign the payments yourself.

Every agent uses **only `gpt-6-luna` through Portkey**. Agents can only *prepare* payments; money moves only when a person approves it on the board.

## Layout

```
hw5/
├── AI_prompts.md          log of the prompts I typed, one section per problem
├── requirements.txt       Python packages (MCP server + backend)
├── .env.example           copy to .env and add PORTKEY_API_KEY (the real .env is not in git)
├── .mcp.json              registers the MCP server for a vibe coder (Claude Code, Cursor…)
├── data/
│   ├── campus_customs.db       original shop database (never modified; used to reset)
│   └── campus_customs_new.db   working copy the app reads and writes (left as it was after my full run)
├── mcp_server/            server.py (14 tools), README.md, smoke_test.py
├── backend/               main.py (FastAPI), team.py (agents + delegation), models.py, prompts/ (one per agent)
├── frontend/              React + Vite + TypeScript dashboard
└── output/                harness.md, design.md, desk_tickets.html, resolved_board.html,
                           resolved_tickets.json, audit_trail.json, mcp_smoke.json, github_url.txt
```

## Setup (once)

```bash
cd hw5
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env          # then put your key after PORTKEY_API_KEY=
cd frontend && npm install && cd ..
```

(No `uv`? Use `python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt`.)

## 1. Get a clean working database

The app only ever touches `data/campus_customs_new.db`. To start clean, copy the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db
chmod u+w data/campus_customs_new.db
```

Once the backend is running you can do the same thing with the **↺ Reset shop** button on the board, or with `curl -X POST http://localhost:8000/api/reset`.

**Always reset before a full three-ticket run.** The committed working copy is the state after my run (checking at $152), so a fresh run needs the original values back ($3,400, invoice 501 open, rent due 2026-09-02).

## 2. Start the MCP server

You don't have to start it by hand for the app. The backend launches `mcp_server/server.py` itself over stdio (one process for the life of the backend). To run it on its own, or to test it:

```bash
.venv/bin/python mcp_server/server.py        # stdio MCP server on data/campus_customs_new.db
.venv/bin/python mcp_server/smoke_test.py    # calls the tools and checks them against SQL
```

To hook it to a vibe coder, open the `hw5/` folder in it; `.mcp.json` registers the server as `campus-customs`.

## 3. Start the FastAPI backend

```bash
cd backend
../.venv/bin/uvicorn main:app --reload --port 8000
```

(Or `source ../.venv/bin/activate` first and run `uvicorn main:app --reload --port 8000`.) It serves `http://localhost:8000` and lets the Vite page (`http://localhost:5173`) call it. `GET /api/health` should show `"model": "gpt-6-luna"` and `"portkey_key_set": true`. The routes are listed in `output/harness.md`.

## 4. Start the React board

```bash
cd frontend
npm run dev
```

It opens `http://localhost:5173` in your browser. The board talks to the backend at `http://localhost:8000`.

## 5. Full three-ticket run

1. Reset the database (step 1 or the **Reset shop** button). Checking should read **$3,400.00**.
2. Pick ticket **101** and press **Run the team**. Watch the floor until the slip is stamped **RESOLVED**. Then do the same for **102** and **103**, one at a time.
3. In **Needs your signature**, type your name under "Signing as" and approve what you want paid. The checking balance drops as each payment goes through. A purchase from a vendor with an unpaid invoice, or anything that would push checking below $0, is refused.

Command-line alternative, without the board: `.venv/bin/python -m backend.run_team --all --reset` (approvals still have to be done on the board).

Every agent step, every reset and every human approval is **appended** to `output/audit_trail.json`, which is never wiped.

## What happened in my run

All three tickets resolved. I approved invoice 501 ($840), a 1-tee purchase order ($8) and rent ($2,400), so checking went **$3,400 → $152**, which matches `cash_accounts`. The 12-hoodie restock ($264) and a duplicate invoice-501 payment were refused by the pay tools. The details are in `output/desk_tickets.html` (Expected vs Actual, Cash and Reflection tabs), `output/resolved_tickets.json` and `output/resolved_board.html`.

## Guardrails

- **No agent can move money.** `pay_with_approval` and `purchase_with_approval` are never given to an agent. Only the backend's approve routes call them, and they require a named person.
- **No negative balances.** The pay tools refuse if cash can't cover the payment, and each runs as one database transaction.
- **Vendors with an unpaid invoice won't ship,** so purchases from them are refused until the invoice is paid.
- **No email, no vendor calls.** Customer replies stay on the board as drafts.
- **Token limits.** One run at a time; per ticket at most 40 model calls, 60 tool calls, 250k tokens and 8 hand-offs, with delegation at most 3 deep.

More in `output/harness.md` (tables, MCP tools, the five agents, API routes, dashboard, safety) and `output/design.md` (the dashboard look).
