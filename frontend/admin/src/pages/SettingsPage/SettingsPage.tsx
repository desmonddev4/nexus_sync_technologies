import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Save } from 'lucide-react'
import { getEscalationPolicy, updateEscalationPolicy } from '../../api/operations'
import type { EscalationPolicy } from '../../types/api'
import './SettingsPage.css'

interface PolicyDraft {
  initial_notification_timeout_minutes: number
  retry_interval_minutes: number
  max_retry_attempts: number
  escalate_to_coordinator_after_minutes: number
  require_operator_acknowledgement: boolean
  allow_simulation_escalation: boolean
  notes: string
}

export function SettingsPage() {
  const [policy, setPolicy] = useState<EscalationPolicy | null>(null)
  const [draft, setDraft] = useState<PolicyDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getEscalationPolicy()
      .then((current) => {
        setPolicy(current)
        setDraft({
          initial_notification_timeout_minutes: current.initial_notification_timeout_minutes,
          retry_interval_minutes: current.retry_interval_minutes,
          max_retry_attempts: current.max_retry_attempts,
          escalate_to_coordinator_after_minutes: current.escalate_to_coordinator_after_minutes,
          require_operator_acknowledgement: current.require_operator_acknowledgement,
          allow_simulation_escalation: current.allow_simulation_escalation,
          notes: current.notes || '',
        })
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setBusy(true)
    setError('')
    try {
      const updated = await updateEscalationPolicy(draft)
      setPolicy(updated)
      setDraft({
        initial_notification_timeout_minutes: updated.initial_notification_timeout_minutes,
        retry_interval_minutes: updated.retry_interval_minutes,
        max_retry_attempts: updated.max_retry_attempts,
        escalate_to_coordinator_after_minutes: updated.escalate_to_coordinator_after_minutes,
        require_operator_acknowledgement: updated.require_operator_acknowledgement,
        allow_simulation_escalation: updated.allow_simulation_escalation,
        notes: updated.notes || '',
      })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update escalation policy.')
    } finally {
      setBusy(false)
    }
  }

  if (loading || !draft) return <div className="settings-loading">Loading escalation policy…</div>

  return (
    <div className="settings-page">
      <header className="page-heading">
        <div>
          <p className="page-eyebrow">OPERATIONS / SETTINGS</p>
          <h1>Escalation policy</h1>
          <p className="page-subtitle">Configure retry behavior, escalation timing, and acknowledgement requirements.</p>
        </div>
        <span className="settings-meta">Updated {policy?.updated_at ? new Date(policy.updated_at).toLocaleString() : '—'}</span>
      </header>

      {error && <div className="page-error" role="alert">{error}</div>}

      <section className="detail-panel">
        <div className="detail-panel-heading">
          <div>
            <p className="page-eyebrow">NOTIFICATION ESCALATION</p>
            <h2>Operational configuration</h2>
          </div>
        </div>

        <form className="settings-form" onSubmit={handleSubmit}>
          <label>
            Initial notification timeout (minutes)
            <input type="number" min={1} max={60} value={draft.initial_notification_timeout_minutes} onChange={(event) => setDraft({ ...draft, initial_notification_timeout_minutes: Number(event.target.value) })} />
          </label>
          <label>
            Retry interval (minutes)
            <input type="number" min={1} max={60} value={draft.retry_interval_minutes} onChange={(event) => setDraft({ ...draft, retry_interval_minutes: Number(event.target.value) })} />
          </label>
          <label>
            Max retry attempts
            <input type="number" min={1} max={20} value={draft.max_retry_attempts} onChange={(event) => setDraft({ ...draft, max_retry_attempts: Number(event.target.value) })} />
          </label>
          <label>
            Escalate to coordinator after (minutes)
            <input type="number" min={1} max={180} value={draft.escalate_to_coordinator_after_minutes} onChange={(event) => setDraft({ ...draft, escalate_to_coordinator_after_minutes: Number(event.target.value) })} />
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={draft.require_operator_acknowledgement} onChange={(event) => setDraft({ ...draft, require_operator_acknowledgement: event.target.checked })} />
            Require operator acknowledgement before closure
          </label>
          <label className="checkbox-row">
            <input type="checkbox" checked={draft.allow_simulation_escalation} onChange={(event) => setDraft({ ...draft, allow_simulation_escalation: event.target.checked })} />
            Allow escalation workflows for simulated incidents
          </label>
          <label>
            Notes
            <textarea value={draft.notes} onChange={(event) => setDraft({ ...draft, notes: event.target.value })} placeholder="Document policy rationale and operational guidance..." />
          </label>
          <button type="submit" disabled={busy}><Save size={15} /> Save policy</button>
        </form>
      </section>
    </div>
  )
}
