import { money } from '../derive'
import type { Approval } from '../types'

const KIND: Record<Approval['kind'], { label: string; stamp: string; verb: string }> = {
  payment: { label: 'Payment', stamp: 'Paid', verb: 'Approve & pay' },
  purchase_order: { label: 'Purchase order', stamp: 'Ordered', verb: 'Approve purchase' },
  discount: { label: 'Discount', stamp: 'Approved', verb: 'Approve discount' },
}

interface Props {
  approvals: Approval[]
  ticketId: number | null
  signer: string
  onSigner: (s: string) => void
  onApprove: (a: Approval) => void
  busy: string | null
  errors: Record<string, string>
  showAll: boolean
  onShowAll: (v: boolean) => void
}

/** The sign-off tray: what the agents prepared that only a person can OK.
 *  Payments and purchases move cash only when someone signs here. */
export function SignOffTray({ approvals, ticketId, signer, onSigner, onApprove, busy, errors, showAll, onShowAll }: Props) {
  const list = approvals
    .filter((a) => showAll || a.ticket_id === ticketId)
    .sort((x, y) => Number(x.status === 'approved') - Number(y.status === 'approved') || y.proposed_at.localeCompare(x.proposed_at))
  const pendingAll = approvals.filter((a) => a.status === 'pending').length
  return (
    <section className="tray">
      <div className="section-head">
        <h3>Needs your signature</h3>
        <label className="toggle">
          <input type="checkbox" checked={showAll} onChange={(e) => onShowAll(e.target.checked)} /> all tickets ({pendingAll})
        </label>
      </div>
      <label className="signer">
        <span>Signing as</span>
        <input value={signer} placeholder="Your name" onChange={(e) => onSigner(e.target.value)} maxLength={60} />
      </label>
      <div className="tray-list">
        {list.length === 0 && (
          <p className="empty">{showAll ? 'Nothing waiting for a signature.' : 'Nothing to sign for this ticket.'} Agents can only prepare money moves. They land here for a person.</p>
        )}
        {list.map((a) => {
          const k = KIND[a.kind]
          const done = a.status === 'approved'
          return (
            <article key={a.approval_id} className={`chit kind-${a.kind} ${done ? 'done' : ''}`}>
              <div className="chit-top">
                <span className="chit-kind">{k.label}</span>
                <span className="chit-ticket">#{a.ticket_id}</span>
              </div>
              <div className="chit-amount">{a.amount != null ? money(a.amount) : '—'}</div>
              <p className="chit-summary">{a.summary}</p>
              {a.reason && <p className="chit-reason">{a.reason}</p>}
              {(errors[a.approval_id] ?? a.last_refusal) && <p className="chit-error">✕ Refused: {(errors[a.approval_id] ?? a.last_refusal)!.replace(/^Refused:\s*/, '')}</p>}
              {done ? (
                <div className="chit-signed">signed by {a.approved_by}</div>
              ) : (
                <button className="btn-sign" disabled={busy === a.approval_id} onClick={() => onApprove(a)}>
                  {busy === a.approval_id ? 'Signing…' : `${k.verb}${a.amount != null && a.kind !== 'discount' ? ` ${money(a.amount)}` : ''}`}
                </button>
              )}
              {done && <span className={`stamp chit-stamp stamp-${a.kind}`}>{k.stamp}</span>}
            </article>
          )
        })}
      </div>
    </section>
  )
}
