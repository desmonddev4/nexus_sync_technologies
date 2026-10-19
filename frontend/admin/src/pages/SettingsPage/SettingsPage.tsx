import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { BellRing, RotateCcw, Save, Settings2, ShieldCheck } from 'lucide-react'
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

function toDraft(policy: EscalationPolicy): PolicyDraft {
  return {
    initial_notification_timeout_minutes: policy.initial_notification_timeout_minutes,
    retry_interval_minutes: policy.retry_interval_minutes,
    max_retry_attempts: policy.max_retry_attempts,
    escalate_to_coordinator_after_minutes: policy.escalate_to_coordinator_after_minutes,
    require_operator_acknowledgement: policy.require_operator_acknowledgement,
    allow_simulation_escalation: policy.allow_simulation_escalation,
    notes: policy.notes || '',
  }
}

/** Number input and slider kept in sync, within the same limits the form always had. */
function PolicyNumber({
  label, unit, value, min, max, onChange,
}: { label: string; unit: string; value: number; min: number; max: number; onChange: (value: number) => void }) {
  const clamped = Math.min(max, Math.max(min, value || min))
  const pct = ((clamped - min) / (max - min)) * 100
  return (
    <label className="policy-number">
      <span className="policy-number__label">{label}</span>
      <span className="policy-number__row">
        <input type="number" min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} />
        <em>{unit}</em>
      </span>
      <input
        className="policy-range"
        type="range"
        min={min}
        max={max}
        value={clamped}
        style={{ ['--pct' as string]: `${pct}%` }}
        onChange={(event) => onChange(Number(event.target.value))}
        aria-label={`${label} slider`}
      />
      <span className="policy-number__scale"><span>{min}</span><span>{max}</span></span>
    </label>
  )
}

export function SettingsPage() {
  const [policy, setPolicy] = useState<EscalationPolicy | null>(null)
  const [draft, setDraft] = useState<PolicyDraft | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    getEscalationPolicy()
      .then((current) => {
        setPolicy(current)
        setDraft(toDraft(current))
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    setBusy(true)
    setError('')
    setSaved(false)
    try {
      const updated = await updateEscalationPolicy(draft)
      setPolicy(updated)
      setDraft(toDraft(updated))
      setSaved(true)
      window.setTimeout(() => setSaved(false), 2400)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update escalation policy.')
    } finally {
      setBusy(false)
    }
  }

  if (loading || !draft) {
    return (
      <div className="ui-page" aria-busy="true" aria-label="Loading escalation policy">
        <div className="ui-skeleton" style={{ height: 70 }} />
        <div className="ui-skeleton" style={{ height: 360 }} />
      </div>
    )
  }

  const dirty = policy ? JSON.stringify(draft) !== JSON.stringify(toDraft(policy)) : false
  const set = <K extends keyof PolicyDraft>(key: K, value: PolicyDraft[K]) => setDraft({ ...draft, [key]: value })

  return (
    <div className="ui-page settings-page">
      <header className="ui-head">
        <div>
          <h1>Escalation policy</h1>
          <p>Configure retry behavior, escalation timing, and acknowledgement requirements.</p>
        </div>
        <span className="ui-pill">Updated {policy?.updated_at ? new Date(policy.updated_at).toLocaleString() : '—'}</span>
      </header>

      {error && <div className="ui-error" role="alert">{error}</div>}

      <form className="settings-form" onSubmit={handleSubmit}>
        <section className="ui-panel">
          <div className="ui-panel__head"><h2><span className="ui-panel__icon"><BellRing size={16} /></span> Timing and retries</h2></div>
          <div className="policy-grid">
            <PolicyNumber label="Initial notification timeout (minutes)" unit="min" min={1} max={60} value={draft.initial_notification_timeout_minutes} onChange={(v) => set('initial_notification_timeout_minutes', v)} />
            <PolicyNumber label="Retry interval (minutes)" unit="min" min={1} max={60} value={draft.retry_interval_minutes} onChange={(v) => set('retry_interval_minutes', v)} />
            <PolicyNumber label="Max retry attempts" unit="tries" min={1} max={20} value={draft.max_retry_attempts} onChange={(v) => set('max_retry_attempts', v)} />
            <PolicyNumber label="Escalate to coordinator after (minutes)" unit="min" min={1} max={180} value={draft.escalate_to_coordinator_after_minutes} onChange={(v) => set('escalate_to_coordinator_after_minutes', v)} />
          </div>
        </section>

        <section className="ui-panel">
          <div className="ui-panel__head"><h2><span className="ui-panel__icon"><ShieldCheck size={16} /></span> Safeguards</h2></div>
          <div className="policy-switches">
            <label className="ui-switch"><input type="checkbox" role="switch" checked={draft.require_operator_acknowledgement} onChange={(event) => set('require_operator_acknowledgement', event.target.checked)} /><span className="ui-switch__track" /><span>Require operator acknowledgement before closure</span></label>
            <label className="ui-switch"><input type="checkbox" role="switch" checked={draft.allow_simulation_escalation} onChange={(event) => set('allow_simulation_escalation', event.target.checked)} /><span className="ui-switch__track" /><span>Allow escalation workflows for simulated incidents</span></label>
          </div>
        </section>

        <section className="ui-panel">
          <div className="ui-panel__head"><h2><span className="ui-panel__icon"><Settings2 size={16} /></span> Notes</h2></div>
          <label className="ui-field">
            Policy notes
            <textarea value={draft.notes} onChange={(event) => set('notes', event.target.value)} placeholder="Document policy rationale and operational guidance..." />
          </label>
        </section>

        {/* Appears whenever there are unsaved changes (or briefly after saving) */}
        <div className={`settings-bar${dirty || saved ? ' is-visible' : ''}${saved && !dirty ? ' is-saved' : ''}`} role="status" aria-live="polite">
          <span>{saved && !dirty ? 'Policy saved' : 'You have unsaved changes'}</span>
          <div>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => policy && setDraft(toDraft(policy))} disabled={!dirty || busy}><RotateCcw size={14} /> Discard</button>
            <button type="submit" className={`ui-btn ui-btn--sm${busy ? ' is-busy' : ''}`} disabled={busy || !dirty}><Save size={15} /> Save policy</button>
          </div>
        </div>
      </form>
    </div>
  )
}