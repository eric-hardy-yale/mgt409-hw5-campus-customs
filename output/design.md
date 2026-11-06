# Campus Customs Ops Desk: design notes

The dashboard lives in `frontend/` (React + Vite + TypeScript). Start the backend from `backend/` with `uvicorn main:app --reload --port 8000`, then run `npm run dev` in `frontend/`. It opens at `http://localhost:5173` and talks to the backend at `http://localhost:8000`, which allows that origin through CORS.

## The idea

I didn't want this to look like a stock admin page with a table and some buttons. Campus Customs is a little print shop on Chapel Street. The person sitting at this desk is running a counter, handling paper order slips, a cash drawer and bills that need a signature. So the whole page borrows from that: warm paper background, navy ink, brass trim, and a cash register in the corner. It still has to be clear, though. Every piece of it answers one of the questions you actually have while the agents work: what's on the board, who is working on it right now, what did they decide, what do I have to sign, and how much money is left.

## Layout

Three columns under a navy header, read left to right like the work flows:

1. **The board (left).** Each ticket is a paper order slip with a perforated tear-off top edge, a big serif "No. 101" and a colored tag for the type (customer order, rent notice, discount request). It also shows who asked, what for, and the SKU, size and qty or the lease. You click a slip to pick it, and the picked one slides out with a navy edge, like pulling it off the spike.
2. **The ticket and the floor (center).** The top card shows the picked ticket with the customer's note in an italic quote and one big **Run the team** button. Under it is **the floor**, the heart of the page. Under that is **Who did what**.
3. **Sign-off and radio (right).** A dark tray called **Needs your signature** holds the approval chits. Under it is the **Floor radio**, a dark live log of every step. On a laptop-width screen this column drops under the board, so nothing gets squeezed.

## How the agents read differently

On the floor, the five agents sit at stations like people around a shop: the Boss at the head, Inventory and Customer Service on the wings, Accounting and Facilities in front. Each one has its own color and its own icon, and they're used the same way everywhere on the page (floor, summary cards, radio, chips):

- **Boss:** navy, a crown.
- **Inventory:** teal, a box.
- **Accounting:** brass, a coin.
- **Facilities:** brick, a storefront.
- **Customer Service:** plum, a speech bubble.

Faint dotted lines join every station to every other one. That's the full connectivity: anyone can hand work to anyone.

While a ticket runs, each station shows what that agent is doing *right now*:

- **A small status line:** THINKING, CALLING CHECK_STOCK, WAITING ON ACCOUNTING, REPORTED BACK, or SAT THIS ONE OUT.
- **A speech bubble:** what it just said or was asked, plus the exact tool call it's making, e.g. `check_stock(sku=CC-HOOD-NAVY, size=M, qty_needed=20)`.
- **The disc:** it pulses while the agent is working and gets a green check when it's done.

When one agent hands work to another, a curved line in the sender's color lights up with marching dashes and a dot travels along it toward whoever got the work. Each direction bends to its own side, so Boss → Accounting and Accounting → Boss never sit on top of each other. A small "Hand-offs" strip at the bottom of the floor lists them in words (for example "Accounting → Inventory").

When the run is over, agents that never got called fade to grey with "sat this one out." I think that's actually one of the most useful bits. Problem 6 said plans that send every specialist on every ticket score low, and here you can see at a glance that, say, Facilities stayed home on the hoodie ticket.

**Who did what** is the after-action summary, one card per agent with a stripe in its color. It shows who asked it, its answer, what it recommends, the MCP tools it used (with counts), who it handed work to, and its steps and tokens. Agents that weren't used drop to the bottom as dashed outlines. Customer Service's card shows the customer reply as an actual little letter on lined paper, marked "DRAFT · NOT SENT", because the shop rule is that drafts stay on the board.

The **Floor radio** is the full play-by-play for the picked ticket. It shows timestamps, each agent's name in its color, tool calls in blue code, results under them, hand-offs in gold, refusals and errors in red, and the Boss's final call highlighted. A red **ON AIR** light blinks while a run is live and goes back to "quiet" after. It scrolls itself so the newest line is always in view.

## How resolved tickets show up

When the run finishes, the backend marks the ticket resolved and a green **RESOLVED** rubber stamp thumps onto the slip: it scales down and lands tilted, a bit faded like real ink. The pill changes to "Resolved" and the header count updates ("1 open · 2 resolved"). If the agents left something for a person, the slip also says "✍ 2 to sign," so a resolved ticket never hides money that still needs a decision. While the team is working, the slip says "Agents on it" with a brass marching stripe along the bottom, and the button turns into a spinner.

## How cash shows up

The checking balance sits in the top-right as a **cash register display**: dark glass with glowing green digits and an "as of" date from `cash_accounts`. When a person approves a payment, the digits roll down to the new balance and the amount that left (like **−$840.00**) floats up off the display in red. You see the money leave instead of just a number changing. If checking drops under $500 the digits turn amber as a warning. That matters here because paying invoice 501 and the rent leaves $160.

## Approvals feel like signing

Only a person can move money, so I made approving feel like signing something, not clicking a random button:

- **Sign in once.** You type your name once in "Signing as" in a handwriting-style serif. It's required: the button refuses until there's a name, and the backend records it as `approved_by`.
- **Each request is a chit.** It's color-coded on the left edge: red for payments, teal for purchase orders, plum for discounts. It shows the amount big and the reason underneath.
- **The button says exactly what happens:** "Approve & pay $840.00", "Approve purchase $264.00".
- **Once signed, it gets a stamp:** **PAID**, **ORDERED** or **APPROVED**, plus "signed by …".
- **Refusals are explained right on the chit.** If the backend refuses, for example "Bulldog Print Co won't ship while invoice 501 is unpaid", the reason appears in red on that chit, so you know what to do first.

## Small things that make it nicer to sit at

- The shop date in the header is the shop's "today" (`desk.date_today`, Mon Aug 31, 2026), not the real date, since that's what decides what's overdue.
- A chip in the header always shows `gpt-6-luna · 5 agents`, so it's clear which model is doing the work.
- If the backend is down or there's no Portkey key, a plain banner says exactly what to do.
- **Reset shop** asks before it wipes anything and is disabled while a run is going.
- Only one run at a time, and the page says so if you try a second one.
- It polls quickly while agents work and slowly when the floor is quiet.
- It respects "reduce motion" settings (all animation off), and it stacks into one column on narrow screens.
- No extra UI libraries: plain React and one CSS file, so it loads fast and everything on screen is something I chose.
