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
      <span className="empty-state__icon"><Icon size={22} aria-hidden="true" /></span>
      <strong>{title}</strong>
      <p>{detail}</p>
    </div>
  )
}