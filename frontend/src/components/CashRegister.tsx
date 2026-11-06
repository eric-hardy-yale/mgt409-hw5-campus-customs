import { useEffect, useRef, useState } from 'react'
import { money } from '../derive'
import type { Cash } from '../types'

/** The checking balance as a register display. When an approved payment lands,
 *  the digits roll down to the new balance and the amount that left floats off. */
export function CashRegister({ cash }: { cash: Cash | null }) {
  const target = cash?.balance ?? null
  const [shown, setShown] = useState<number | null>(target)
  const [delta, setDelta] = useState<{ amount: number; id: number } | null>(null)
  const prev = useRef<number | null>(target)

  useEffect(() => {
    if (target == null) return
    const from = prev.current
    prev.current = target
    if (from == null || from === target) { setShown(target); return }
    const id = Date.now()
    setDelta({ amount: target - from, id })
    const clear = setTimeout(() => setDelta((d) => (d?.id === id ? null : d)), 2600)
    const start = performance.now()
    const dur = 1100
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur)
      const ease = 1 - Math.pow(1 - t, 3)
      setShown(from + (target - from) * ease)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => { cancelAnimationFrame(raf); clearTimeout(clear) }
  }, [target])

  const low = target != null && target < 500
  return (
    <div className={`register ${low ? 'low' : ''}`} title="Checking balance from cash_accounts">
      <div className="register-label">
        <span>Checking</span>
        <span className="register-asof">{cash ? `as of ${cash.as_of}` : '—'}</span>
      </div>
      <div className="register-display">
        <span className="register-digits">{shown == null ? '— — —' : money(shown)}</span>
        {delta && (
          <span key={delta.id} className={`register-delta ${delta.amount < 0 ? 'down' : 'up'}`}>
            {delta.amount < 0 ? '−' : '+'}{money(Math.abs(delta.amount))}
          </span>
        )}
      </div>
    </div>
  )
}
