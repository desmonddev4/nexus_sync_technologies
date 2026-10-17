import './StatusBadge.css'

const labels: Record<string, string> = {
  created: 'New',
  acknowledged: 'Acknowledged',
  responder_assigned: 'Responder assigned',
  dispatch_requested: 'Request recorded',
  dispatch_confirmed: 'Confirmation recorded',
  responder_en_route: 'En route',
  arrived: 'Arrived',
  resolved: 'Resolved',
  closed: 'Closed',
  declined: 'Declined',
  cancelled: 'Cancelled',
  queued: 'Queued',
  submitted: 'Submitted',
  delivered: 'Delivered',
  failed: 'Failed',
  acknowledged_notification: 'Acknowledged',
  available: 'Available',
  unavailable: 'Unavailable',
  on_call: 'On call',
  out_of_service: 'Out of service',
  verified: 'Verified',
  unverified: 'Unverified',
  simulated: 'Simulation only',
  active: 'Active',
  inactive: 'Inactive',
}

interface StatusBadgeProps {
  value: string
  tone?: 'default' | 'danger' | 'success' | 'warning' | 'info'
}

export function StatusBadge({ value, tone }: StatusBadgeProps) {
  const inferredTone = tone || getTone(value)
  return <span className={`status-badge status-badge--${inferredTone}`}>{labels[value] || value.replaceAll('_', ' ')}</span>
}

function getTone(value: string): NonNullable<StatusBadgeProps['tone']> {
  if (['created', 'failed', 'cancelled', 'declined', 'inactive', 'unverified'].includes(value)) return 'danger'
  if (['delivered', 'resolved', 'closed', 'verified', 'available', 'active'].includes(value)) return 'success'
  if (['dispatch_requested', 'queued', 'on_call', 'simulated'].includes(value)) return 'warning'
  if (['responder_en_route', 'dispatch_confirmed', 'submitted'].includes(value)) return 'info'
  return 'default'
}