import { useEffect, useRef, useState } from 'react'
import type { LucideIcon } from 'lucide-react'
import './MetricTile.css'

interface MetricTileProps {
  label: string
  value: string | number
  detail: string
  icon: LucideIcon
  tone: 'coral' | 'green' | 'amber' | 'blue'
}

/** Eases numbers up to their value; skips the animation for reduced-motion users. */
function useCountUp(target: number, enabled: boolean) {
  const [display, setDisplay] = useState(0)
  const current = useRef(0)

  useEffect(() => {
    if (!enabled) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      current.current = target
      setDisplay(target)
      return
    }
    const from = current.current
    const start = performance.now()
    const duration = 700
    let frame = 0

    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1)
      const eased = 1 - Math.pow(1 - progress, 3)
      const next = Math.round(from + (target - from) * eased)
      current.current = next
      setDisplay(next)
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [target, enabled])

  return display
}

export function MetricTile({ label, value, detail, icon: Icon, tone }: MetricTileProps) {
  const isNumber = typeof value === 'number'
  const animated = useCountUp(isNumber ? value : 0, isNumber)

  return (
    <section className={`metric-tile metric-tile--${tone}`}>
      <div className="metric-tile__top">
        <span>{label}</span>
        <span className="metric-tile__icon">
          <Icon size={17} strokeWidth={1.9} aria-hidden="true" />
        </span>
      </div>
      <strong>{isNumber ? animated : value}</strong>
      <small>{detail}</small>
    </section>
  )
}