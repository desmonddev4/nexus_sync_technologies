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
      <span className="empty-state__tile" aria-hidden="true">
        <Icon size={22} strokeWidth={1.8} />
      </span>
      <strong>{title}</strong>
      <span className="empty-state__rule" aria-hidden="true" />
      <p>{detail}</p>
    </div>
  )
}