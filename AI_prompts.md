# AI Prompts Log — Campus Customs Multi-Agent Operations (HW5)

One section per problem: the problem number and title, the prompt I typed, and a follow-up prompt if the first attempt fell short (with one sentence on what was lacking).

## Assignment overview

**Prompt:**
> Campus Customs Multi-Agent Operations is the agentic team that runs the shop. Open tickets land on a board — customer orders, rent, unpaid bills, discount requests, whatever the shop has to handle. You will build three pieces that talk to eachother: an MCP server, a FastAPI backend with a multi-agent team, and a React dashboard so a human can watch the agents at work and approve requests. Your agent team has full connectivity — any agent may delegate tasks to any other agent for help.

**Prompt (the agent team):**
> you will build these agents:
> Boss — reads each ticket, decides who should work on it, and makes final calls
> Inventory — checks stock by SKU and size, spots shortfalls, and figures out which vendor can restock
> Accounting — watches cash and invoices, checks margins, and prepares payments or purchase orders for human approval
> Facilities — handles the shop space side (leases, rent, etc.)
> Customer Service — drafts messages for customers

**Prompt (data and shop rules):**
> Download data.zip and unzip so you have data/campus_customs.db. That file is the original shop database. Tables include desk, tickets, inventory, pricing, vendors, leases, cash_accounts, payments, and invoices. Your tools will update the database as tickets get resolved. Make a copy of the database file called data/campus_customs_new.db and point your MCP server and backend at that working copy. Keep campus_customs.db untouched so you can reset when you want to restart resolving the tickets.
>
> Rules of this shop: desk.date_today is "today" for the shop and decides what is overdue. Vendor lead times come from the vendors table. A vendor will not ship new product while they still have an open unpaid invoice. Human approval is required for any payments, and if a payment is made the relevant table gets updated. If there is not enough cash the pay tool must refuse — no negative balances. Cash only goes out (no revenue). Reset the database to the original values before a full run. Do not email customers or call real vendors; drafts stay on the board. Use PORTKEY_API_KEY and only gpt-6-luna through Portkey for every agent.

**Result:** Gave the vibe coder the big picture before any building: a ticket board, an MCP server, a FastAPI backend running a fully connected team of five agents (Boss, Inventory, Accounting, Facilities, Customer Service), and a React dashboard where a human watches and approves. No code yet; each piece gets built in its own problem.

## Problem 1: Vibe coder prompts

**Prompt:**
> Create AI_prompts.md at the start of the assignment and keep it updated as you work. This file is the log of what i typed to your vibe coder.

**Result:** Created `hw5/AI_prompts.md` as the log for this assignment. The vibe coder adds a section here as each problem is worked.

**Follow-up prompt:**
> Put one section for each problem. Each section must include: the problem number and title; at least one prompt you typed, in your own words as much as possible; one follow-up prompt if you needed it (and one sentence on what was lacking after the first).

**What was lacking after the first:** The first prompt didn't say what each section should contain, so I spelled out the required parts.

## Problem 2: Study the Campus Customs database

**Prompt:**
> Open data/campus_customs.db and look through every table and its fields. Copy the original file to data/campus_customs_new.db — later problems update that working copy.

**Follow-up prompt:**
> check the downloads folder titled "data 2"

**What was lacking after the first:** The vibe coder couldn't find the HW5 database (it only found the HW4 one, which has the wrong tables), so I had to tell it which folder the file was in.

**Result:** Copied `~/Downloads/data 2/campus_customs.db` (same file as in `data (2).zip`) to `hw5/data/campus_customs.db` and made it read-only, then copied it to the working file `hw5/data/campus_customs_new.db`. Went through all 9 tables:
- `desk`: today is 2026-08-31.
- `tickets`: 3 open: #101 a customer wants a white tee in S, #102 a rent notice, #103 the Yale AI Club wants 20 navy hoodies in M at a bulk discount.
- `inventory` (SKU + size): tee S has 0 and hoodie M has 8, so #101 is short 1 and #103 is short 12. Mugs are at 0 too, but no ticket asks for them.
- `pricing`: unit cost vs list price (hoodie $22 / $58, tee $8 / $28).
- `vendors`: Bulldog Print Co (apparel, 5 days), Elm City Gifts (mugs and small goods, 3 days), QuickShip CT (courier, 1 day).
- `invoices`: #501, $840 to Bulldog Print Co, due 2026-08-28 and still open. It's overdue, so Bulldog won't ship any apparel until it's paid.
- `leases`: Chapel Street shop, $2,400 rent due 2026-09-02.
- `cash_accounts`: checking has $3,400. Paying the invoice and the rent ($3,240) leaves $160.
- `payments`: empty. Each payment row records `approved_by`.

## Problem 3: Build the MCP server

**Prompt:**
> Write an MCP server in mcp_server/ using FastMCP. It will talk to data/campus_customs_new.db.
>
> write three tools you know you will need for the tickets in the database. Keep the names clear. Never invent any data, only use information in the database.
>
> In output/harness.md, list each of your three MCP tools. For every tool include: which table it reads, which ticket it helps unlock (101, 102, or 103), and one sentence on why that tool is the right one for that ticket.

**Follow-up prompt:**
> Vague lines like "reads inventory" score low — tie the tool to the ticket. Also add a short mcp_server/README.md file that explains what the MCP server is for, which database file it uses, and the three tools it has.

**What was lacking after the first:** The harness entries could have been generic table descriptions, so I asked for each tool to be tied to its specific ticket, plus a README for the server.

**Result:** Built `mcp_server/server.py` (FastMCP 4) with three read-only tools: `check_stock` (inventory → tickets 101 and 103), `get_rent_status` (leases + desk + cash_accounts → ticket 102) and `get_price_and_margin` (pricing → ticket 103). Each one returns only database values or arithmetic on them, and errors out if a SKU, size or lease isn't on file. Tested every tool on the three real tickets against a scratch copy, over stdio too. `output/harness.md` ties each tool to its ticket with the actual numbers, and `mcp_server/README.md` explains the server, its database and its tools.

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt:**
> add the MCP server to this project. Save the connection JSON text in .mcp.json at the project root (or however you save local MCP server lists).

**Result:** Saved the connection as server `campus-customs` in `hw5/.mcp.json` (relative paths, so it works from the `hw5/` folder on any machine). Also added it to the workspace's own `.mcp.json`, next to my other two servers, so Claude Code can load it here. Checked that both entries start the server and answer a tool call (rent for lease 1 = $2,400 due 2026-09-02). The tools appear in the vibe coder after the session restarts and the server is approved.

**Follow-up prompt:**
> With the vibe coder connected, test each of your three MCP tools. Save the evidence in output/mcp_smoke.json.

**What was lacking after the first:** Saving the connection only proved the server starts; I needed proof that each tool actually returns the right answer for its ticket.

**Result:** The vibe coder's session had started before `.mcp.json` changed, so the server wasn't loaded as its own tools yet. Instead it wrote `mcp_server/smoke_test.py`, which launches the server exactly as `.mcp.json` says, calls each tool over MCP, and checks every answer against a direct SQL query. 7/7 passed: 101 tee S = 0 on hand (short 1); 102 rent $2,400 due in 2 days, $1,000 left after paying; 103 hoodie M = 8 on hand (short 12); 103 hoodie $22 cost / $58 list ($36 margin). A size, lease and SKU that don't exist were refused, not made up, and the database file was unchanged. Evidence is in `output/mcp_smoke.json`.

Then, in a new session with the server connected, the vibe coder (Claude Code) called the `campus-customs` tools directly as its own tools. Each output below matches the script results and a read-only SQL check of `data/campus_customs_new.db`. Both database files still have the same sha256. Saved under `vibe_coder_calls` in `output/mcp_smoke.json`.

| Prompt to the vibe coder | Tool | Tool output | DB check |
|---|---|---|---|
| Ticket 101: `check_stock(sku="CC-TEE-WHITE", size="S", qty_needed=1)` | `check_stock` | Classic Bulldog Tee S: 0 on hand, Aisle B, need 1, short 1, can't fill from stock | inventory row: qty 0, Aisle B ✓ |
| Ticket 102: `get_rent_status(lease_id=1)` | `get_rent_status` | Chapel Street shop, Elm City Properties: $2,400 due 2026-09-02, today 2026-08-31, 2 days away, not overdue; checking $3,400 covers it, $1,000 left | leases id 1: 2400.0, 2026-09-02; checking 3400.0 on 2026-08-31; desk today 2026-08-31 ✓ |
| Ticket 103: `check_stock(sku="CC-HOOD-NAVY", size="M", qty_needed=20)` | `check_stock` | Basic Hoodie Big Yale M: 8 on hand, Aisle A, need 20, short 12, can't fill from stock | inventory row: qty 8, Aisle A ✓ |
| Ticket 103: `get_price_and_margin(sku="CC-HOOD-NAVY")` | `get_price_and_margin` | $22 cost, $58 list, $36 margin per unit, 62.1% max discount before a loss | pricing row: 22.0 / 58.0 ✓ |
| One input that isn't in the database: `check_stock(sku="CC-HOOD-NAVY", size="XXL")` | `check_stock` | Refused: "SKU CC-HOOD-NAVY has no size XXL; sizes on file: L, M, S, XL" | hoodie sizes in inventory: L, M, S, XL (no XXL) ✓ |

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:**
> Build the agentic team for Campus Customs using PydanticAI: Boss, Inventory, Accounting, Facilities, and Customer Service. Include prompts, models, and agent loops so they can delegate work to each other with full connectivity.

**Follow-up prompt:**
> Put the agent prompts in backend/prompts/ — one file per agent. Put data types in backend/models.py, and the agent files under backend/ (your layout can vary as long as the five roles are clear). Use your PORTKEY_API_KEY and only gpt-6-luna for every agent. Write each prompt in your own words with the shop rules that agent needs. More detailed prompts that cover all aspects of an agent's work and scope score higher than a short generic prompt. Add any tools the agents need to your MCP server so they can work on the open tickets. Shop facts come from the MCP server over data/campus_customs_new.db — do not invent a second shop-tools layer that bypasses MCP.

**What was lacking after the first:** The first prompt didn't say where the files go, which model to use, how detailed the prompts should be, or that every shop fact has to come through the MCP server.

**Follow-up prompt:**
> Wire the agents so they append to output/audit_trail.json as they run: for each agent-loop step, record enough to audit later. Append to this file — do not wipe it each run. In output/harness.md, list each agent and each MCP tool (including ones you add in this problem) along with which table the tool uses. Also add a short safety section: the guardrails a real business would want when agents touch real customers and real money, plus limits that keep token use in check. Update mcp_server/README.md so the tool list matches what you have now.

**What was lacking after the second:** The team worked, but there was no record of what each agent did, and the harness and README still listed only the first three tools.

**Result:**
- **Agents:** Built the five-agent team in `backend/` with PydanticAI. Each agent has a detailed prompt file in `backend/prompts/` with the shop rules for its role. The data types are in `backend/models.py`. Every agent runs on `gpt-6-luna` through Portkey, and that model is fixed in `backend/config.py`.
- **Delegation:** Every agent has a `delegate(to, task)` tool, so any agent can hand work to any other. Guardrails stop loops, delegation deeper than 3, more than 8 hand-offs per ticket, and team-wide spend over 40 model calls / 250k tokens.
- **MCP tools:** Grew the server from 3 to 12 tools: tickets, vendors, invoices, cash, payment and purchase-order prep, ticket status, and a pay tool. The pay tool needs a named human approver, refuses negative balances, and is given to no agent.
- **Audit trail:** Every agent-loop step (prompt, tool calls with arguments, tool results, delegations, tokens, final answer) is appended to `output/audit_trail.json`. The file is never wiped.
- **Docs:** `output/harness.md` lists each agent and each tool with its tables, plus a safety and token-limits section. `mcp_server/README.md` now lists all 12 tools.
- **Testing:**
  - Tested every new tool on a scratch copy. Invoice 501 is $840, 3 days overdue. Rent is $2,400, due in 2 days. Paying both leaves $160, and a third payment is refused.
  - Tested the team's wiring offline with a scripted stand-in model, without calling AI. Each agent saw only its own tools, and specialists delegated to each other. Self-delegation and handing work back up the chain were refused, the Boss couldn't reach the pay tool, and the two real database files didn't change.
  - Not run live with `gpt-6-luna` yet, because `hw5/.env` has no `PORTKEY_API_KEY`.

## Problem 6: Plan the three tickets

**Prompt:**
> Before you wire the backend, write down what you expect the team to do on each open ticket. Build output/desk_tickets.html — a page you can double-click with one tab per ticket (101, 102, and 103).

**Follow-up prompt:**
> Also add empty Cash and Reflection tabs for later problems (leave them blank or with a short "coming later" note for now). On each ticket tab, fill an Expected section only (leave room for an Actual section you will fill after you run the agents).

**What was lacking after the first:** The first prompt didn't mention the Cash and Reflection tabs, or that each ticket tab needs a separate Actual section left empty for later.

**Result:** Built `output/desk_tickets.html`, one file with no scripts or internet needed, so it opens with a double-click. It has tabs for Ticket 101, 102, 103, Cash and Reflection; Cash and Reflection say "Coming later." Each ticket tab shows the ticket, an Expected plan and an empty Actual box. The plan gives who the Boss calls first and why, each delegation with one hand-off between two specialists, the MCP tools I expect, the approvals a person should see, and where the ticket should end. I kept each plan lean instead of sending every agent:
- **101:** Boss → Inventory (tee S: 0 on hand, short 1, Bulldog blocked by invoice 501). Inventory → Accounting (prepare the $840 payment, $3,400 → $2,560). Boss → Customer Service (draft to Tauhid). Facilities not called.
- **102:** Boss → Facilities ($2,400 due 2026-09-02, $1,000 left). Facilities → Accounting (invoice 501 competes; both leave $160). Inventory and Customer Service not called.
- **103:** Boss → Accounting ($22 / $58 / $36 margin, 62.1% max). Accounting → Inventory (8 on hand, short 12, restock $264). Accounting should catch that $160 left after both bills can't cover the $264 restock. Boss → Customer Service (draft, no discount promised). Facilities not called.

The backend was already wired in Problem 5, so this plan is what I'll compare a live run against in Problem 9.

**Follow-up prompt:**
> For each ticket's Expected section, write in your own words: Who the Boss should call first, and why. All the agent delegations you expect — not "Boss calls everyone". Which MCP tools you expect that run to use. Plans that send every specialist on every ticket score low. You will compare this plan to what actually happens when your agents resolve the three tickets.

**What was lacking after the second:** The page already had the first call, the delegations and the tools. But the tools were one flat list per ticket, so I couldn't check later which agent was supposed to call which one.

**Result:** Each ticket's "MCP tools I expect" is now a small table of each agent and the tools it should call, with a few words on what for:
- **101:** 7 tools.
- **102:** 6 tools.
- **103:** 8 tools.

I also checked that every planned tool is one that agent actually has in the backend.

## Problem 7: Backend routes

**Prompt:**
> Your React frontend dashboard (the next problem) needs a backend it can call. In backend/main.py, use FastAPI and add routes that do the following: Return the three tickets and whether each is open or resolved. Take a ticket id and run your agent team on that ticket. Return recent agent events — what each agent said and which tools they used — so the board can refresh. Approve a payment or purchase after a human clicks approve (agents only prepare the pay; this route is what actually changes cash). Return the current checking balance from cash_accounts. Reset the database to the original values when you want to try a fresh run.

**Follow-up prompt:**
> From the backend/ folder, start the server with: uvicorn main:app --reload --port 8000. This turns on your backend at http://localhost:8000 so the frontend dashboard can call those routes. In output/harness.md, list each route in one line (what URL / what it does).

**What was lacking after the first:** The first prompt didn't say how the server gets started (from `backend/` as `main:app` on port 8000), so imports had to work from that folder. It also didn't say to list the routes in the harness.

**Result:**
- **Routes:** Built `backend/main.py` with FastAPI. It lists tickets with open/resolved, runs the team on a ticket (in the background, one run at a time), and returns recent agent events from the audit trail (who said what, which tools with which arguments). It also lists what the agents prepared for approval, approves it, returns the checking balance, and resets the working database.
- **Approvals:** The approve routes are the only place cash changes. They need a person's name and use two human-only MCP tools no agent has: `pay_with_approval`, plus a new `purchase_with_approval` for restocks. I also added `list_tickets`, so the board can show resolved tickets.
- **Tests:** Tested every route on a scratch copy with a scripted stand-in model, with no AI called.
  - The tee restock was refused while invoice 501 was unpaid.
  - An agent's name as approver was rejected, and a second approval of the same item returned 409.
  - Paying 501, then the restock, then rent took checking from $3,400 → $2,560 → $2,552 → $152. Paying rent again was refused because the balance would go negative.
  - Reset brought it back to $3,400.
- **Startup:** It starts from `backend/` with `uvicorn main:app`. Without `PORTKEY_API_KEY` it refuses to run a ticket with a clear message. Each route is one line in `output/harness.md`.

## Problem 8: Agent dashboard

**Prompt:**
> Build the frontend dashboard in frontend/ with React + Vite + TypeScript. The page should call the routes you built in Problem 7. At minimum the board should: List all three tickets. Let you pick one ticket and start the agent team on it. Show each agent and what they are saying / doing while the ticket runs. Mark a ticket resolved when the run finishes. Show a short summary of what each agent did on that ticket. Let a human approve a pay or purchase when asked. Show the checking balance (it should drop after an approved pay). Make the dashboard look good. Be creative with the layout and feel — this is a real desk people would want to sit at, so put thought into how it looks.

**Follow-up prompt:**
> Tell the front end to talk to your backend at http://localhost:8000. On the backend, allow the Vite page origin (usually http://localhost:5173) so the browser is allowed to call those routes. Start the board with: npm run dev. This opens the React desk in your browser so you can pick tickets and watch agents. Write output/design.md with what you chose for the dashboard look (layout, how agents read differently, how resolved tickets and cash show up) and why — including the creative choices that make it feel special and something humans would actually enjoy using.

**What was lacking after the first:** The first prompt didn't say where the backend lives (port 8000), that the browser needs CORS to call it, how the board starts, or that the design choices had to be written up.

**Result:**
- **The board:** Built the "Campus Customs Ops Desk" in `frontend/` (React + Vite + TypeScript, no UI libraries). Tickets are paper order slips that get a RESOLVED rubber stamp.
- **The floor:** the five agents sit at stations, each with its own color and icon, with live status and speech bubbles showing what they're saying and which MCP tool they're calling. Hand-off lines light up as one agent delegates to another, and agents that weren't needed fade out as "sat this one out".
- **Panels:** a "Who did what" card per agent, and a dark "Needs your signature" tray where you type your name to approve (PAID / ORDERED stamps). A "Floor radio" log shows every step, and the checking balance is a cash register that rolls down when a payment goes through.
- **Backend changes:** a finished run now marks the ticket resolved, and a new `/api/tickets/{id}/summary` route feeds the summary cards. I also changed the Boss prompt so it no longer sets the final status itself.
- **Testing:** Checked it in the browser against a scripted demo backend on a scratch database, with no AI called and no real data touched. Tickets 103 and 101 ran live on the floor and got stamped resolved. The tee purchase was refused while invoice 501 was unpaid. Approving the $840 payment took the register from $3,400 to $2,560.
- **Docs:** `output/design.md` explains the look and why; `output/harness.md` has a Dashboard section.

## Problem 9: Run the three tickets and fill in what actually happened

**Prompt:**
> Before testing the agents on a full run over the three tickets, reset the working database data/campus_customs_new.db again so you start clean. Note the starting checking balance. Then run all three tickets on the board (101, 102, 103) until each is resolved. Open output/desk_tickets.html from Problem 6. On each ticket tab, fill the Actual section from this run: which agents worked, what they delegated, and which tools they used. Keep your Expected section so you can compare the two.

**Follow-up prompt:**
> please create it with your hw4 key, do this for me

**What was lacking after the first:** The run couldn't start: `hw5/.env` had no Portkey key yet, so I had the vibe coder copy my hw4 key line into it (it never printed the key).

**Follow-up prompt:**
> On the Cash tab of the same output/desk_tickets.html, itemize the money: Starting checking balance (after the reset). For each ticket: how cash changed when that ticket resolved, and why (which pay / purchase, dollar amount). Ending checking balance — it must match cash_accounts in the working database. Wrong cash math loses points even if the board shows every ticket resolved. Also save: output/resolved_tickets.json — for each ticket: id, final status, short outcome, what each agent contributed, and any human approvals. output/resolved_board.html — a page you can double-click with a screenshot of your React board for each resolved ticket (101, 102, and 103). Append real runs to output/audit_trail.json. Finish output/harness.md so it covers tables, MCP tools, the five agents, API routes, the dashboard, and safety rules.

**What was lacking after the second:** The first prompt only asked for the Actual sections. It didn't cover the money, the JSON summary, the screenshots, or finishing the harness.

**Result:**
- **Reset and runs:** Reset from the board, so the starting checking balance was **$3,400.00**. Ran 101, 102 and 103 live on gpt-6-luna from the dashboard, one at a time, and all three got stamped resolved (52 model calls, about 117k tokens).
- **My approvals:** When the vibe coder asked what to sign, I said pay invoice 501, the tee and rent, then try the hoodies, and sign as "Eric".
  - Paid invoice 501 ($840), 1 tee ($8) and rent ($2,400).
  - The 12-hoodie restock ($264) was refused because checking only had $152, and a duplicate 501 payment was refused as already paid.
  - Ending balance **$152.00**, which matches `cash_accounts`.
- **Actual vs Expected:** each Actual section shows who the Boss really called first (it sent two or three agents at once every time), every hand-off with timestamps, and the tools per agent.
- **What the agents got wrong:**
  - They missed the cash squeeze on 103: they thought $2,296 would be left because they never counted the rent.
  - The 103 draft leaked our $22 cost to the club.
- **Files:** saved `resolved_tickets.json` and `resolved_board.html` (six board screenshots embedded: each ticket when it resolved and after sign-off). The audit trail now has the reset, every agent step and every approval, appended.
- **Harness:** `output/harness.md` now covers the tables, the 14 MCP tools, the five agents, the routes, the dashboard, safety, and the run results.

## Problem 10: Reflection

**Prompt:**
> Open output/desk_tickets.html and fill the Reflection tab. Answer in your own vibe, and be detailed and thorough: How would you evaluate the performance of the agents on each ticket and why? For each ticket, how did Actual compare to the Expected plan you wrote earlier? What would have been simpler as one agent with tools — and why? Describe three new problems Campus Customs might face that this agent team could solve with the tools you built. Describe three new problems Campus Customs might face that this agent team could not solve with the tools you built, and explain the tools and agents you would need to solve them. Tie every answer to this app and the three tickets you ran — use the ticket tabs and Cash tab on the same page as your evidence.

**Follow-up prompt:**
> Generic AI essays without Campus Customs details will score low.

**Follow-up prompt:**
> use the attached to create a writing voice that sounds like mine.

**What was lacking after the first:** "Your own vibe" doesn't mean much if the vibe coder has never seen how I write, so I gave it two of my own pieces to build a style guide from. I also made clear the answers had to stay specific to this shop and these three tickets.

**Result:** Saved my style guide as `my_writing_voice.md` (style only) and wrote the Reflection tab in that voice. It has a thesis up front, the plan laid out in threes, evidence then what it means, and a closing that comes back to the start. Every point cites a ticket tab or a Cash row:
- **Grades:** 101 gets an A− (right facts and order, but 16 model calls to sell one $28 tee). 102 gets a B (smartest answer, but Facilities and Accounting asked each other the same thing in the same second). 103 gets a C (missed the $152 cash squeeze, no discount decided, the draft leaked our cost).
- **Plan vs actual:** a table showing the Boss fanned out every time instead of the relay I planned.
- **One agent would be simpler for:** rent, the tee, and above all cash planning across tickets.
- **Three problems the team can solve with these tools:** a cap order, a mug restock that fits in $152, and an early warning on October rent.
- **Three it can't, and what it would need:** getting paid (Sales/Billing agent and order tools), planning cash across the board (Treasury agent with `forecast_cash`), and closing the loop on messages and stock (Fulfillment agent and a Comms reviewer, with human-approved sending).

## Problem 11: Push to GitHub

**Prompt:**
> Push your code to a public GitHub repository so graders can clone it. Submit the repo URL to Canvas, and also put it in output/github_url.txt. Do not push your real .env to the GitHub repo. Do include both database files under data/ (the original and your working copy) so graders can run your app easily. [expected file layout] README should explain: copy original DB to the working copy when you need a clean run, start MCP server, start FastAPI backend, start the React board, reset the DB before a full three-ticket run.

**Result:**
- **Repo:** Pushed `hw5/` to the public repo https://github.com/eric-hardy-yale/mgt409-hw5-campus-customs, and the URL is in `output/github_url.txt`.
- **Before pushing:** checked that the real `.env` was git-ignored and that my Portkey key appeared in none of the 60+ committed files. `.venv`, `node_modules` and lock files are ignored too.
- **What's included:** both databases (the original and the working copy as my run left it, at $152), `.env.example`, `.mcp.json`, a top-level `requirements.txt`, and every output file.
- **README:** covers setup, copying the original DB over the working copy, the MCP server, the FastAPI backend (`uvicorn main:app --reload --port 8000` from `backend/`), the React board (`npm run dev`), and resetting before a full three-ticket run.
- **Still to do:** I submit the URL on Canvas myself.
