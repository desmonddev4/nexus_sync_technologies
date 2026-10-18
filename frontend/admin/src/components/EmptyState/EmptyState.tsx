import type { LucideIcon } from 'lucide-react'
import './EmptyState.css'

interface EmptyStateProps {
  icon: LucideIcon
  title: string
  detail: string
}

export function EmptyState({ icon: Icon, title, detail }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state__orb" aria-hidden="true">
        <i className="empty-state__ring empty-state__ring--a" />
        <i className="empty-state__ring empty-state__ring--b" />
        <span className="empty-state__icon"><Icon size={22} /></span>
      </span>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  )
}