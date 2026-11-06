import { AGENTS, AgentIcon } from '../agents'
import { clip } from '../derive'
import type { AgentSummary, TicketSummary } from '../types'

function Facts({ output }: { output: Record<string, unknown> | null }) {
  const facts = (output?.facts as { detail: string; source: string }[] | undefined) ?? []
  if (!facts.length) return null
  return (
    <ul className="facts">
      {facts.slice(0, 4).map((f, i) => (
        <li key={i}>{f.detail} <span className="src">{f.source}</span></li>
      ))}
    </ul>
  )
}

function Card({ s }: { s: AgentSummary }) {
  const a = AGENTS[s.agent]
  const tools = Object.entries(s.tools)
  // the letter lives on Customer Service's card (the Boss just passes it along)
  const draft = s.agent === 'customer_service' ? ((s.output?.customer_draft as string | undefined) ?? null) : null
  const recommendation = (s.output?.recommendation as string | undefined) ?? null
  return (
    <article className={`did ${s.used ? '' : 'unused'}`} style={{ ['--c' as string]: a.color, ['--soft' as string]: a.soft }}>
      <header>
        <span className="did-icon"><AgentIcon agent={s.agent} size={18} /></span>
        <div>
          <h4>{a.name}</h4>
          <span className="did-meta">
            {s.used ? (s.asked_by.length ? `asked by ${[...new Set(s.asked_by)].join(', ')}` : 'ran the ticket') : 'sat this one out'}
          </span>
        </div>
      </header>
      {s.used && (
        <>
          {s.summary && <p className="did-summary">{clip(s.summary, s.agent === 'boss' ? 420 : 260)}</p>}
          {recommendation && s.agent !== 'boss' && <p className="did-rec"><b>Recommends:</b> {clip(recommendation, 160)}</p>}
          {s.agent === 'boss' && <Facts output={s.output} />}
          <div className="did-row">
            {tools.length ? tools.map(([t, n]) => <code key={t} className="tool-chip">{t}{n > 1 ? ` ×${n}` : ''}</code>) : <span className="muted">no MCP tools</span>}
          </div>
          {s.delegated_to.length > 0 && (
            <div className="did-row handoffs">
              {s.delegated_to.map((d, i) => (
                <span key={i} className="handoff-chip" style={{ ['--to' as string]: AGENTS[d.to]?.color }} title={d.task}>→ {d.name}</span>
              ))}
            </div>
          )}
          {draft && (
            <div className="letter">
              <span className="letter-mark">Draft · not sent</span>
              <p>{draft}</p>
            </div>
          )}
          {s.error && <p className="did-error">{s.error}</p>}
          <footer>{s.steps} step{s.steps === 1 ? '' : 's'} · {(s.input_tokens + s.output_tokens).toLocaleString()} tokens</footer>
        </>
      )}
    </article>
  )
}

/** "Who did what" — one card per agent for the selected ticket's latest run. */
export function AgentSummaries({ summary }: { summary: TicketSummary | null }) {
  if (!summary || summary.status === 'not_run') {
    return (
      <section className="summaries empty-state">
        <h3>Who did what</h3>
        <p>Nobody has worked this ticket yet. Press <b>Run the team</b> and the summary fills in here.</p>
      </section>
    )
  }
  const order = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']
  const cards = [...summary.agents].sort((x, y) => Number(y.used) - Number(x.used) || order.indexOf(x.agent) - order.indexOf(y.agent))
  const used = summary.agents.filter((a) => a.used).length
  return (
    <section className="summaries">
      <div className="section-head">
        <h3>Who did what</h3>
        <span className="muted">
          {used} of 5 agents worked it
          {summary.usage ? ` · ${summary.usage.requests} model calls · ${(summary.usage.input_tokens + summary.usage.output_tokens).toLocaleString()} tokens` : ''}
        </span>
      </div>
      <div className="did-grid">{cards.map((s) => <Card key={s.agent} s={s} />)}</div>
    </section>
  )
}
