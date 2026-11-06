import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { API_BASE, ApiError, api } from './api'
import { AgentSummaries } from './components/AgentSummaries'
import { CashRegister } from './components/CashRegister'
import { Feed } from './components/Feed'
import { Floor } from './components/Floor'
import { SignOffTray } from './components/SignOffTray'
import { TicketRail } from './components/TicketRail'
import { agentStates, edges, feedRows, latestRunId, money } from './derive'
import type { AgentEvent, Approval, Cash, Health, Ticket, TicketSummary } from './types'

interface Toast { id: number; text: string; tone: 'ok' | 'bad' | 'info' }

const TYPE_VERB: Record<string, string> = {
  customer_order: 'wants',
  rent_notice: 'sent a notice',
  price_override: 'is asking for a deal',
}

function prettyDate(iso?: string) {
  if (!iso) return '—'
  const d = new Date(`${iso}T12:00:00`)
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })
}

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [down, setDown] = useState(false)
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [cash, setCash] = useState<Cash | null>(null)
  const [events, setEvents] = useState<AgentEvent[]>([])
  const since = useRef(-1)
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [summary, setSummary] = useState<TicketSummary | null>(null)
  const [run, setRun] = useState<{ runId: string; ticketId: number } | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [signer, setSigner] = useState(() => localStorage.getItem('cc-signer') ?? '')
  const [busy, setBusy] = useState<string | null>(null)
  const [approveErrors, setApproveErrors] = useState<Record<string, string>>({})
  const [showAll, setShowAll] = useState(false)

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200)
  }, [])

  // --- loading ------------------------------------------------------------------
  const refresh = useCallback(async () => {
    try {
      const [h, t, c, a] = await Promise.all([api.health(), api.tickets(), api.cash(), api.approvals()])
      setHealth(h); setTickets(t); setCash(c); setApprovals(a); setDown(false)
      setSelected((s) => s ?? t[0]?.id ?? null)
      return h
    } catch (e) {
      if (e instanceof ApiError && e.status === 0) setDown(true)
      return null
    }
  }, [])

  const pulling = useRef(false)
  const pullEvents = useCallback(async () => {
    if (pulling.current) return // one fetch at a time, or overlapping polls would add the same events twice
    pulling.current = true
    try {
      const r = await api.events(since.current)
      // the audit file only grows; if it got shorter something replaced it, so start over
      if (r.next_since < since.current) { since.current = -1; setEvents([]); return }
      since.current = r.next_since
      if (r.events.length) {
        setEvents((ev) => {
          const last = ev.length ? ev[ev.length - 1].seq : -1
          const fresh = r.events.filter((e) => e.seq > last)
          return fresh.length ? [...ev, ...fresh] : ev
        })
      }
    } catch { /* backend down: refresh() shows the banner */ } finally {
      pulling.current = false
    }
  }, [])

  const loadSummary = useCallback(async (ticketId: number | null) => {
    if (ticketId == null) return
    try { setSummary(await api.summary(ticketId)) } catch { /* ignore */ }
  }, [])

  useEffect(() => { refresh(); pullEvents() }, [refresh, pullEvents])
  useEffect(() => { setSummary(null); loadSummary(selected) }, [selected, loadSummary])

  // pick up a run started elsewhere (e.g. from the CLI) so the board still lights up
  const runningId = run?.runId ?? health?.run_in_progress ?? null
  const runningTicket = useMemo(() => {
    if (run) return run.ticketId
    if (!runningId) return null
    return events.find((e) => e.run_id === runningId)?.ticket_id ?? null
  }, [run, runningId, events])

  // --- polling: fast while agents work, slow when the floor is quiet ----------------
  useEffect(() => {
    const fast = runningId != null
    const ev = setInterval(pullEvents, fast ? 700 : 3000)
    const rf = setInterval(refresh, fast ? 2500 : 8000)
    return () => { clearInterval(ev); clearInterval(rf) }
  }, [runningId, pullEvents, refresh])

  useEffect(() => {
    if (!run) return
    const iv = setInterval(async () => {
      try {
        const info = await api.runInfo(run.runId)
        if (selected === run.ticketId) loadSummary(run.ticketId)
        if (info.status === 'running') return
        clearInterval(iv)
        await pullEvents(); await refresh(); await loadSummary(run.ticketId)
        if (info.status === 'done') toast(`Ticket #${run.ticketId} resolved. The team is done.`, 'ok')
        else toast(`Ticket #${run.ticketId}: ${info.error ?? 'run failed'}`, 'bad')
        setRun(null)
      } catch { /* keep trying */ }
    }, 1200)
    return () => clearInterval(iv)
  }, [run, selected, pullEvents, refresh, loadSummary, toast])

  // --- actions ------------------------------------------------------------------
  const startRun = async (ticketId: number) => {
    try {
      const info = await api.run(ticketId)
      setRun({ runId: info.run_id, ticketId })
      setSummary(null)
      toast(`Team is on ticket #${ticketId}`, 'info')
      setHealth((h) => (h ? { ...h, run_in_progress: info.run_id } : h))
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), 'bad')
    }
  }

  const approve = async (a: Approval) => {
    const name = signer.trim()
    if (name.length < 2) { toast('Type your name in "Signing as" first. Only a person can approve.', 'bad'); return }
    setBusy(a.approval_id)
    setApproveErrors((m) => { const n = { ...m }; delete n[a.approval_id]; return n })
    try {
      const r = await api.approve(a.approval_id, name)
      const amt = (r.result?.amount as number | undefined) ?? a.amount
      if (a.kind === 'discount') toast(`Discount approved by ${name}. No cash moved.`, 'ok')
      else toast(`${a.kind === 'payment' ? 'Paid' : 'Ordered'} ${money(amt)}, signed by ${name}`, 'ok')
      await refresh(); await pullEvents()
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      setApproveErrors((m) => ({ ...m, [a.approval_id]: msg }))
      toast(msg, 'bad')
      await pullEvents()
    } finally { setBusy(null) }
  }

  const reset = async () => {
    if (!window.confirm('Reset the working database to the original values? Payments, purchases and ticket statuses go back to the start. The audit trail is kept.')) return
    try {
      await api.reset()
      await refresh(); await pullEvents(); await loadSummary(selected)
      toast('Database reset. Fresh start.', 'info')
    } catch (e) { toast(e instanceof Error ? e.message : String(e), 'bad') }
  }

  useEffect(() => { localStorage.setItem('cc-signer', signer) }, [signer])

  // --- derived view state ---------------------------------------------------------
  const ticket = tickets.find((t) => t.id === selected) ?? null
  const runId = selected != null ? latestRunId(events, selected) : null
  const runEvents = useMemo(() => (runId ? events.filter((e) => e.run_id === runId) : []), [events, runId])
  const isRunningHere = runningTicket != null && runningTicket === selected
  const live = useMemo(() => agentStates(runEvents, isRunningHere), [runEvents, isRunningHere])
  const wires = useMemo(() => edges(runEvents), [runEvents])
  const feed = useMemo(() => {
    if (selected == null) return []
    const firstSeq = runEvents[0]?.seq ?? Infinity
    const humans = events.filter((e) => e.agent === 'human' && e.ticket_id === selected && e.seq > firstSeq)
    return feedRows([...runEvents, ...humans].sort((a, b) => a.seq - b.seq))
  }, [events, runEvents, selected])
  const pending = useMemo(() => {
    const m: Record<number, number> = {}
    for (const a of approvals) if (a.status === 'pending') m[a.ticket_id] = (m[a.ticket_id] ?? 0) + 1
    return m
  }, [approvals])

  const keyMissing = health && !health.portkey_key_set

  return (
    <div className="desk">
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">CC</div>
          <div>
            <h1>Campus Customs <span>Ops Desk</span></h1>
            <p>Chapel Street, New Haven · shop date <b>{prettyDate(cash?.today)}</b></p>
          </div>
        </div>
        <div className="topbar-mid">
          <span className="chip model-chip" title="Every agent runs on this model through Portkey">● {health?.model ?? 'gpt-6-luna'} · 5 agents</span>
          <span className={`chip ${runningId ? 'chip-live' : ''}`}>{runningId ? `Run ${runningId} live` : 'Floor quiet'}</span>
        </div>
        <div className="topbar-right">
          <CashRegister cash={cash} />
          <button className="btn-ghost" onClick={reset} disabled={runningId != null} title="Copy the original database over the working copy">↺ Reset shop</button>
        </div>
      </header>

      {down && <div className="banner bad">Can't reach the backend at {API_BASE}. Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code>.</div>}
      {keyMissing && <div className="banner warn">No <code>PORTKEY_API_KEY</code> in <code>hw5/.env</code>, so the team can't run. Add it and restart the backend.</div>}

      <main className="layout">
        <TicketRail tickets={tickets} selected={selected} runningTicket={runningTicket} pending={pending} onSelect={setSelected} />

        <div className="center">
          {ticket ? (
            <section className="ticket-head">
              <div className="ticket-title">
                <span className="ticket-no">#{ticket.id}</span>
                <div>
                  <h2>{ticket.subject}</h2>
                  <p>{ticket.requester} {TYPE_VERB[ticket.type] ?? ''}{ticket.sku ? ` · ${ticket.qty} × ${ticket.sku} in ${ticket.size}` : ''}{ticket.lease_id ? ` · lease #${ticket.lease_id}` : ''}{ticket.invoice_id ? ` · linked to invoice #${ticket.invoice_id}` : ''}</p>
                </div>
              </div>
              {ticket.notes && <blockquote>{ticket.notes.split('\n')[0]}</blockquote>}
              <div className="ticket-actions">
                <button className="btn-run" onClick={() => startRun(ticket.id)} disabled={runningId != null || !!keyMissing || down}>
                  {isRunningHere ? <><span className="spinner" /> Team is working…</> : ticket.resolved ? '↻ Run the team again' : '▶ Run the team'}
                </button>
                <span className="muted">
                  {isRunningHere ? 'Watch the floor. Hand-offs light up as they happen.'
                    : ticket.resolved ? `Resolved${summary?.run_id ? ` by run ${summary.run_id}` : ''}.`
                    : runningId ? 'Another ticket is running. One at a time keeps the spend sane.' : 'The Boss reads it first and decides who to call.'}
                </span>
              </div>
            </section>
          ) : <section className="ticket-head"><p className="muted">Pick a ticket from the board.</p></section>}

          <Floor live={live} edges={wires} running={isRunningHere} />
          <AgentSummaries summary={summary} />
        </div>

        <div className="right">
          <SignOffTray
            approvals={approvals} ticketId={selected} signer={signer} onSigner={setSigner}
            onApprove={approve} busy={busy} errors={approveErrors} showAll={showAll} onShowAll={setShowAll}
          />
          <Feed rows={feed} running={isRunningHere} />
        </div>
      </main>

      <div className="toasts">
        {toasts.map((t) => <div key={t.id} className={`toast ${t.tone}`}>{t.text}</div>)}
      </div>
    </div>
  )
}
