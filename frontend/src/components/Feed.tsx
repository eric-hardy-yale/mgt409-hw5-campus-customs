import { useEffect, useRef } from 'react'
import { AGENTS } from '../agents'
import { clock, type FeedRow } from '../derive'
import type { AgentKey } from '../types'

const who = (w: FeedRow['who']) =>
  w === 'human' ? { name: 'You', color: '#8fe0a6' } : w === 'system' ? { name: 'Desk', color: '#a49e90' } : { name: AGENTS[w as AgentKey].name, color: AGENTS[w as AgentKey].glow }

/** The radio: every step of the run as it happens — what each agent said, which MCP
 *  tool it called with which arguments, what came back, and every hand-off. */
export function Feed({ rows, running }: { rows: FeedRow[]; running: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = box.current
    if (el) el.scrollTop = el.scrollHeight
  }, [rows.length])
  return (
    <section className="feed">
      <div className="section-head">
        <h3>Floor radio</h3>
        <span className={`on-air ${running ? 'live' : ''}`}>{running ? 'on air' : 'quiet'}</span>
      </div>
      <div className="feed-box" ref={box}>
        {rows.length === 0 && <p className="feed-empty">Quiet on the floor. Run the team and every step shows up here.</p>}
        {rows.map((r) => {
          const w = who(r.who)
          return (
            <div key={r.key} className={`feed-row k-${r.kind}`}>
              <span className="feed-time">{clock(r.ts)}</span>
              <span className="feed-dot" style={{ background: w.color }} />
              <div className="feed-body">
                <span className="feed-who" style={{ color: w.color }}>{w.name}</span>{' '}
                {r.kind === 'tool' ? <code className="feed-tool">{r.text}({r.sub})</code>
                  : r.kind === 'result' || r.kind === 'retry' ? <><span className="feed-text">{r.kind === 'retry' ? '⚠ ' : '↳ '}{r.text}</span> <code className="feed-result">{r.sub}</code></>
                  : r.kind === 'said' ? <q className="feed-said">{r.text}</q>
                  : <><span className="feed-text">{r.text}</span>{r.sub ? <span className="feed-sub"> — {r.sub}</span> : null}</>}
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
