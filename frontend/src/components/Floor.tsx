import { AGENTS, AGENT_ORDER, AgentIcon } from '../agents'
import { clip, type AgentLive, type Edge } from '../derive'
import type { AgentKey } from '../types'

const W = 1000
const H = 480

function curve(from: AgentKey, to: AgentKey) {
  const a = AGENTS[from]
  const b = AGENTS[to]
  const mx = (a.x + b.x) / 2
  const my = (a.y + b.y) / 2
  const dx = b.x - a.x
  const dy = b.y - a.y
  const len = Math.hypot(dx, dy) || 1
  // bend to the right of the direction of travel, so A→B and B→A don't overlap
  const cx = mx + (-dy / len) * 38
  const cy = my + (dx / len) * 38
  return { d: `M ${a.x} ${a.y} Q ${cx} ${cy} ${b.x} ${b.y}` }
}

const PAIRS: [AgentKey, AgentKey][] = AGENT_ORDER.flatMap((a, i) => AGENT_ORDER.slice(i + 1).map((b) => [a, b] as [AgentKey, AgentKey]))

const STATUS_TEXT: Record<AgentLive['status'], string> = {
  idle: 'idle', thinking: 'thinking', tool: 'using a tool', waiting: 'waiting', done: 'done', error: 'error', sat_out: 'sat out',
}

/** The floor: five stations, every one wired to every other (full connectivity).
 *  Hand-offs light up as they happen; the speech bubble shows what each agent is doing. */
export function Floor({ live, edges, running }: { live: Record<AgentKey, AgentLive>; edges: Edge[]; running: boolean }) {
  return (
    <section className={`floor ${running ? 'is-running' : ''}`} aria-label="Agent floor">
      <svg className="floor-wires" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" aria-hidden="true">
        {PAIRS.map(([a, b]) => {
          const p = { x1: AGENTS[a].x, y1: AGENTS[a].y, x2: AGENTS[b].x, y2: AGENTS[b].y }
          return <line key={`${a}-${b}`} {...p} className="wire-idle" vectorEffect="non-scaling-stroke" />
        })}
        {edges.map((e) => {
          const { d } = curve(e.from, e.to)
          return (
            <g key={`${e.from}>${e.to}`}>
              <path d={d} className={`wire-used ${e.active ? 'active' : ''}`} stroke={AGENTS[e.from].color} vectorEffect="non-scaling-stroke" />
              {e.active && (
                <circle r="6" fill={AGENTS[e.from].color} className="wire-spark">
                  <animateMotion dur="1.3s" repeatCount="indefinite" path={d} />
                </circle>
              )}
            </g>
          )
        })}
      </svg>

      {edges.some((e) => e.count > 0 || e.refused > 0) && (
        <div className="handoff-strip" aria-label="Hand-offs in this run">
          <span className="strip-label">Hand-offs</span>
          {edges.filter((e) => e.count > 0).map((e) => (
            <span
              key={`lbl-${e.from}>${e.to}`}
              className={`wire-label ${e.active ? 'active' : ''}`}
              style={{ borderColor: AGENTS[e.from].color, color: AGENTS[e.from].color }}
              title={`${AGENTS[e.from].name} handed work to ${AGENTS[e.to].name}`}
            >
              {AGENTS[e.from].name} → {AGENTS[e.to].name}{e.count > 1 ? ` ×${e.count}` : ''}
            </span>
          ))}
          {edges.filter((e) => e.refused > 0).map((e) => (
            <span key={`ref-${e.from}>${e.to}`} className="wire-label refused" title="Blocked by a guardrail (loop, depth or budget)">
              {AGENTS[e.from].name} ⇸ {AGENTS[e.to].name} refused
            </span>
          ))}
        </div>
      )}

      {AGENT_ORDER.map((k) => {
        const a = AGENTS[k]
        const s = live[k]
        return (
          <div
            key={k}
            className={`station st-${s.status} ${k === 'boss' ? 'boss' : ''}`}
            style={{ left: `${(a.x / W) * 100}%`, top: `${(a.y / H) * 100}%`, ['--c' as string]: a.color, ['--soft' as string]: a.soft }}
          >
            <div className="disc"><AgentIcon agent={k} size={k === 'boss' ? 28 : 24} />{s.status === 'done' && <span className="disc-check">✓</span>}</div>
            <div className="station-name">{a.name}</div>
            <div className="station-state">{s.label}</div>
            {(s.line || s.tool) && s.status !== 'sat_out' ? (
              <div className="bubble" aria-label={`${a.name} is ${STATUS_TEXT[s.status]}`}>
                {s.line && <p>{clip(s.line, k === 'boss' ? 220 : 150)}</p>}
                {s.tool && <code>{clip(s.tool, 70)}</code>}
              </div>
            ) : (
              <div className="station-role">{a.role}</div>
            )}
          </div>
        )
      })}
    </section>
  )
}
