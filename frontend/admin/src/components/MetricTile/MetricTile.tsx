import type { LucideIcon } from 'lucide-react'
import './MetricTile.css'

interface MetricTileProps {
  label: string
  value: string | number
  detail: string
  icon: LucideIcon
  tone: 'coral' | 'green' | 'amber' | 'blue'
}

export function MetricTile({ label, value, detail, icon: Icon, tone }: MetricTileProps) {
  return (
    <section className={`metric-tile metric-tile--${tone}`}>
      <div className="metric-tile__top">
        <span>{label}</span>
        <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
      </div>
      <strong>{value}</strong>
      <small>{detail}</small>
    </section>
  )
}