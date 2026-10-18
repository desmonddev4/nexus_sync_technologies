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

type Tone = 'default' | 'danger' | 'success' | 'warning' | 'info'

interface StatusBadgeProps {
  value: string
  tone?: Tone
}

// Tones that mean "something is happening or needs a look" get a pulsing dot.
const livetones = new Set<Tone>(['danger', 'warning', 'info'])

export function StatusBadge({ value, tone }: StatusBadgeProps) {
  const inferredTone = tone || getTone(value)
  const live = livetones.has(inferredTone) && !['failed', 'cancelled', 'declined', 'inactive', 'unverified'].includes(value)
  return (
    <span className={`status-badge status-badge--${inferredTone}${live ? ' is-live' : ''}`}>
      {labels[value] || value.replaceAll('_', ' ')}
    </span>
  )
}

function getTone(value: string): NonNullable<StatusBadgeProps['tone']> {
  if (['created', 'failed', 'cancelled', 'declined', 'inactive', 'unverified'].includes(value)) return 'danger'
  if (['delivered', 'resolved', 'closed', 'verified', 'available', 'active'].includes(value)) return 'success'
  if (['dispatch_requested', 'queued', 'on_call', 'simulated'].includes(value)) return 'warning'
  if (['responder_en_route', 'dispatch_confirmed', 'submitted'].includes(value)) return 'info'
  return 'default'
}