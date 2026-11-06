import type { Ticket } from '../types'

const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Discount request',
}

function details(t: Ticket): string {
  if (t.sku) return `${t.qty ?? '?'} × ${t.sku} · ${t.size ?? ''}`
  if (t.lease_id) return `Lease #${t.lease_id}`
  return ''
}

interface Props {
  tickets: Ticket[]
  selected: number | null
  runningTicket: number | null
  pending: Record<number, number>
  onSelect: (id: number) => void
}

/** The board: each ticket is a paper order slip. Resolved ones get a stamp. */
export function TicketRail({ tickets, selected, runningTicket, pending, onSelect }: Props) {
  return (
    <aside className="rail">
      <div className="rail-head">
        <h2>The board</h2>
        <span className="rail-count">
          {tickets.filter((t) => !t.resolved).length} open · {tickets.filter((t) => t.resolved).length} resolved
        </span>
      </div>
      <div className="slips">
        {tickets.map((t) => {
          const running = runningTicket === t.id
          return (
            <button
              key={t.id}
              className={`slip ${selected === t.id ? 'selected' : ''} ${t.resolved ? 'resolved' : ''} ${running ? 'running' : ''}`}
              onClick={() => onSelect(t.id)}
            >
              <div className="slip-top">
                <span className="slip-no">No. {t.id}</span>
                <span className={`slip-type type-${t.type}`}>{TYPE_LABEL[t.type] ?? t.type}</span>
              </div>
              <div className="slip-who">{t.requester}</div>
              <div className="slip-subject">{t.subject}</div>
              {details(t) && <div className="slip-details">{details(t)}</div>}
              <div className="slip-foot">
                <span className={`state-pill ${running ? 'running' : t.state}`}>
                  {running ? 'Agents on it' : t.resolved ? 'Resolved' : t.status === 'open' ? 'Open' : t.status.replace(/_/g, ' ')}
                </span>
                {pending[t.id] ? <span className="sign-badge">✍ {pending[t.id]} to sign</span> : null}
              </div>
              {t.resolved && <span className="stamp resolved-stamp">Resolved</span>}
              {running && <span className="slip-progress" />}
            </button>
          )
        })}
        {tickets.length === 0 && <p className="empty">No tickets yet.</p>}
      </div>
    </aside>
  )
}
