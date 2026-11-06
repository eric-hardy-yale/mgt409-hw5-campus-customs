// Turns the raw event stream into what the desk shows: each agent's live state,
// the hand-off lines on the floor, and the readable feed.
import { AGENTS, AGENT_ORDER } from './agents'
import type { AgentEvent, AgentKey } from './types'

export type AgentStatus = 'idle' | 'thinking' | 'tool' | 'waiting' | 'done' | 'error' | 'sat_out'

export interface AgentLive {
  status: AgentStatus
  label: string // short state, e.g. "Calling check_stock"
  line: string | null // what it said or is doing, in words
  tool: string | null
  lastSeq: number
}

export interface Edge {
  from: AgentKey
  to: AgentKey
  count: number
  active: boolean
  refused: number
}

export const clip = (s: string, n: number) => (s.length > n ? s.slice(0, n - 1) + '…' : s)

export function fmtArgs(args: Record<string, unknown> | null | undefined): string {
  if (!args) return ''
  return Object.entries(args)
    .map(([k, v]) => `${k}=${typeof v === 'string' ? v : JSON.stringify(v)}`)
    .join(', ')
}

export function nameOf(key: string | null | undefined): string {
  if (!key) return 'someone'
  return key in AGENTS ? AGENTS[key as AgentKey].name : key
}

/** The newest top-level Boss run for a ticket. */
export function latestRunId(events: AgentEvent[], ticketId: number): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    const e = events[i]
    if (e.event === 'run_start' && e.agent === 'boss' && e.chain.length === 1 && e.ticket_id === ticketId) return e.run_id
  }
  return null
}

export function agentStates(runEvents: AgentEvent[], running: boolean): Record<AgentKey, AgentLive> {
  const live = Object.fromEntries(
    AGENT_ORDER.map((k) => [k, { status: 'idle', label: 'Idle', line: null, tool: null, lastSeq: -1 } as AgentLive]),
  ) as Record<AgentKey, AgentLive>

  for (const e of runEvents) {
    if (e.agent === 'human') continue
    const a = live[e.agent]
    a.lastSeq = e.seq
    switch (e.event) {
      case 'run_start':
        a.status = 'thinking'
        a.label = e.chain.length > 1 ? `Asked by ${nameOf(e.chain[e.chain.length - 2])}` : 'Picked up the ticket'
        a.line = e.said ? e.said.replace(/^Ticket #\d+\.\s*Task from [^:]+:\s*/, '') : null
        a.tool = null
        break
      case 'model_request':
        a.status = 'thinking'
        if (e.tool_results.length) {
          const names = e.tool_results.map((r) => r.tool).filter((t) => t && t !== 'delegate')
          if (names.length) a.label = `Reading ${names.join(', ')}`
          else a.label = 'Thinking'
        } else a.label = 'Thinking'
        break
      case 'model_response': {
        const del = e.tools.find((t) => t.tool === 'delegate')
        const tool = e.tools.find((t) => t.tool !== 'delegate')
        if (e.said) a.line = e.said
        if (del) {
          a.status = 'waiting'
          a.label = `Asking ${nameOf(String(del.args?.to ?? ''))}`
          if (!e.said) a.line = String(del.args?.task ?? '')
          a.tool = null
        } else if (tool) {
          a.status = 'tool'
          a.label = `Calling ${tool.tool}`
          a.tool = `${tool.tool}(${fmtArgs(tool.args)})`
        }
        break
      }
      case 'delegation_start':
        a.status = 'waiting'
        a.label = `Waiting on ${nameOf(e.delegation?.to)}`
        break
      case 'delegation_end':
        a.status = 'thinking'
        a.label = `${nameOf(e.delegation?.to)} reported back`
        break
      case 'delegation_refused':
        a.label = `Hand-off to ${nameOf(e.delegation?.to)} refused`
        break
      case 'final_output':
        a.status = 'done'
        a.label = e.agent === 'boss' ? 'Made the call' : 'Reported back'
        a.line = e.said
        a.tool = null
        break
      case 'run_end':
        a.status = 'done'
        break
      case 'error':
        a.status = 'error'
        a.label = 'Hit an error'
        a.line = e.said
        break
    }
  }
  // once a run is over, agents that never showed up "sat this one out"
  const started = runEvents.length > 0
  if (started && !running) {
    for (const k of AGENT_ORDER) if (live[k].lastSeq === -1) { live[k].status = 'sat_out'; live[k].label = 'Sat this one out' }
  }
  return live
}

export function edges(runEvents: AgentEvent[]): Edge[] {
  const map = new Map<string, Edge>()
  const get = (from: AgentKey, to: AgentKey) => {
    const k = `${from}>${to}`
    if (!map.has(k)) map.set(k, { from, to, count: 0, active: false, refused: 0 })
    return map.get(k)!
  }
  for (const e of runEvents) {
    if (e.agent === 'human' || !e.delegation?.to) continue
    const edge = get(e.agent, e.delegation.to)
    if (e.event === 'delegation_start') { edge.count += 1; edge.active = true }
    if (e.event === 'delegation_end') edge.active = false
    if (e.event === 'delegation_refused') edge.refused += 1
  }
  return [...map.values()]
}

export interface FeedRow {
  key: string
  ts: string
  who: AgentKey | 'human' | 'system'
  kind: 'start' | 'said' | 'tool' | 'result' | 'handoff' | 'report' | 'refused' | 'decision' | 'error' | 'approval' | 'reset' | 'retry'
  text: string
  sub?: string
}

const preview = (v: unknown) => clip(typeof v === 'string' ? v : JSON.stringify(v), 150)

export function feedRows(events: AgentEvent[]): FeedRow[] {
  const rows: FeedRow[] = []
  for (const e of events) {
    const who = e.agent
    const base = { ts: e.ts, who } as const
    switch (e.event) {
      case 'run_start':
        if (e.chain.length === 1) rows.push({ ...base, key: `${e.seq}`, kind: 'start', text: `picked up ticket #${e.ticket_id}` })
        break
      case 'model_response':
        if (e.said) rows.push({ ...base, key: `${e.seq}s`, kind: 'said', text: e.said })
        e.tools.forEach((t, i) => {
          if (t.tool === 'delegate') return
          rows.push({ ...base, key: `${e.seq}t${i}`, kind: 'tool', text: t.tool, sub: fmtArgs(t.args) })
        })
        break
      case 'model_request':
        e.tool_results.forEach((r, i) => {
          if (r.tool === 'delegate') return
          const isRetry = typeof r.result === 'string' && /not in|refused|no size|must be|unknown tool/i.test(r.result)
          rows.push({ ...base, key: `${e.seq}r${i}`, kind: isRetry ? 'retry' : 'result', text: r.tool ?? 'result', sub: preview(r.result) })
        })
        break
      case 'delegation_start':
        rows.push({ ...base, key: `${e.seq}`, kind: 'handoff', text: `→ ${nameOf(e.delegation?.to)}`, sub: e.delegation?.task ?? '' })
        break
      case 'delegation_end':
        rows.push({ ...base, key: `${e.seq}`, kind: 'report', text: `${nameOf(e.delegation?.to)} reported back`, sub: e.delegation?.summary ?? e.said ?? '' })
        break
      case 'delegation_refused':
        rows.push({ ...base, key: `${e.seq}`, kind: 'refused', text: `hand-off to ${nameOf(e.delegation?.to)} refused`, sub: e.delegation?.reason ?? '' })
        break
      case 'final_output':
        if (who === 'boss' && e.chain.length === 1) rows.push({ ...base, key: `${e.seq}`, kind: 'decision', text: 'made the call', sub: e.said ?? '' })
        break
      case 'error':
        rows.push({ ...base, key: `${e.seq}`, kind: 'error', text: 'error', sub: e.said ?? '' })
        break
      case 'human_approval':
        rows.push({ ...base, key: `${e.seq}`, kind: 'approval', text: e.said ?? 'approval' })
        break
      case 'db_reset':
        rows.push({ key: `${e.seq}`, ts: e.ts, who: 'system', kind: 'reset', text: 'Database reset to the original values' })
        break
    }
  }
  return rows
}

export const money = (n: number | null | undefined) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })

export const clock = (ts: string) =>
  new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
