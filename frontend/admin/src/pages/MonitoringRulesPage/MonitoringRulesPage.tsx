import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowUpRight, FlaskConical, PlusCircle } from 'lucide-react'
import {
  createMonitoringRule,
  getMonitoringRuleEvaluations,
  getMonitoringRules,
  reviewMonitoringRule,
} from '../../api/operations'
import type { MonitoringRule, MonitoringRuleEvaluation } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './MonitoringRulesPage.css'

interface RuleDraft {
  name: string
  description: string
  measurement_type: string
  operator: 'gt' | 'gte' | 'lt' | 'lte'
  threshold: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  minimum_consecutive_readings: number
  lookback_window_seconds: number
  include_simulated: boolean
  version: string
}

const DEFAULT_DRAFT: RuleDraft = {
  name: '',
  description: '',
  measurement_type: 'heart_rate_bpm',
  operator: 'gt',
  threshold: '100',
  priority: 'high',
  minimum_consecutive_readings: 1,
  lookback_window_seconds: 300,
  include_simulated: false,
  version: 'v1',
}

export function MonitoringRulesPage() {
  const [rules, setRules] = useState<MonitoringRule[]>([])
  const [evaluations, setEvaluations] = useState<MonitoringRuleEvaluation[]>([])
  const [selectedRuleId, setSelectedRuleId] = useState<string>('')
  const [draft, setDraft] = useState<RuleDraft>(DEFAULT_DRAFT)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function refreshRules(selectRuleId?: string) {
    const nextRules = await getMonitoringRules()
    setRules(nextRules)
    const chosen = selectRuleId || selectedRuleId || nextRules[0]?.id || ''
    setSelectedRuleId(chosen)
    if (chosen) {
      setEvaluations(await getMonitoringRuleEvaluations(chosen, 15))
    } else {
      setEvaluations([])
    }
  }

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      getMonitoringRules()
        .then(async (nextRules) => {
          if (!active) return
          setRules(nextRules)
          const chosen = nextRules[0]?.id || ''
          setSelectedRuleId(chosen)
          if (chosen) {
            const nextEvaluations = await getMonitoringRuleEvaluations(chosen, 15)
            if (active) setEvaluations(nextEvaluations)
          } else {
            setEvaluations([])
          }
        })
        .catch((reason: Error) => {
          if (active) setError(reason.message)
        })
        .finally(() => {
          if (active) setLoading(false)
        })
    }, 0)

    return () => {
      active = false
      window.clearTimeout(timer)
    }
  }, [])

  const selectedRule = useMemo(
    () => rules.find((rule) => rule.id === selectedRuleId) || null,
    [rules, selectedRuleId],
  )

  async function handleCreate(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      const created = await createMonitoringRule(draft)
      setDraft(DEFAULT_DRAFT)
      await refreshRules(created.id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to create monitoring rule.')
    } finally {
      setBusy(false)
    }
  }

  async function handleToggle(rule: MonitoringRule, nextEnabled: boolean) {
    setBusy(true)
    setError('')
    try {
      await reviewMonitoringRule(rule.id, nextEnabled)
      await refreshRules(rule.id)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to update rule review state.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="monitoring-rules-page">
      <header className="page-heading">
        <div>
          <p className="page-eyebrow">OPERATIONS / MONITORING</p>
          <h1>Rule management</h1>
          <p className="page-subtitle">Draft, review, and enable clinician-approved rule versions.</p>
        </div>
        <span className="rules-count">{rules.length} rules</span>
      </header>

      {error && <div className="page-error" role="alert">{error}</div>}

      <div className="rules-layout">
        <section className="detail-panel">
          <div className="detail-panel-heading">
            <div>
              <p className="page-eyebrow">CREATE VERSION</p>
              <h2>New monitoring rule</h2>
            </div>
          </div>
          <form className="rule-form" onSubmit={handleCreate}>
            <label>Rule name<input value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} required /></label>
            <label>Description<textarea value={draft.description} onChange={(event) => setDraft({ ...draft, description: event.target.value })} /></label>
            <div className="form-grid">
              <label>Measurement<select value={draft.measurement_type} onChange={(event) => setDraft({ ...draft, measurement_type: event.target.value })}><option value="heart_rate_bpm">Heart rate</option><option value="spo2_percent">SpO2</option><option value="skin_temperature_celsius">Skin temperature</option><option value="body_temperature_celsius">Body temperature</option><option value="systolic_bp_mmhg">Systolic BP</option><option value="diastolic_bp_mmhg">Diastolic BP</option></select></label>
              <label>Operator<select value={draft.operator} onChange={(event) => setDraft({ ...draft, operator: event.target.value as RuleDraft['operator'] })}><option value="gt">&gt;</option><option value="gte">&gt;=</option><option value="lt">&lt;</option><option value="lte">&lt;=</option></select></label>
              <label>Threshold<input value={draft.threshold} onChange={(event) => setDraft({ ...draft, threshold: event.target.value })} required /></label>
              <label>Priority<select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as RuleDraft['priority'] })}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
              <label>Consecutive readings<input type="number" min={1} max={20} value={draft.minimum_consecutive_readings} onChange={(event) => setDraft({ ...draft, minimum_consecutive_readings: Number(event.target.value) })} /></label>
              <label>Lookback seconds<input type="number" min={30} max={86400} value={draft.lookback_window_seconds} onChange={(event) => setDraft({ ...draft, lookback_window_seconds: Number(event.target.value) })} /></label>
              <label>Version<input value={draft.version} onChange={(event) => setDraft({ ...draft, version: event.target.value })} required /></label>
            </div>
            <label className="checkbox-row"><input type="checkbox" checked={draft.include_simulated} onChange={(event) => setDraft({ ...draft, include_simulated: event.target.checked })} /> Include simulated measurements</label>
            <button type="submit" disabled={busy}><PlusCircle size={15} /> Create draft rule</button>
          </form>
        </section>

        <section className="detail-panel">
          <div className="detail-panel-heading"><div><p className="page-eyebrow">RULE VERSIONS</p><h2>Existing rules</h2></div></div>
          {loading ? <div className="loading-row">Loading monitoring rules…</div> : rules.length === 0 ? <EmptyState icon={FlaskConical} title="No rules configured" detail="Create a draft rule to begin monitoring management." /> : (
            <div className="rule-list">
              {rules.map((rule) => (
                <article key={rule.id} className={`rule-row${selectedRuleId === rule.id ? ' is-selected' : ''}`}>
                  <button type="button" className="rule-main" onClick={async () => { setSelectedRuleId(rule.id); setEvaluations(await getMonitoringRuleEvaluations(rule.id, 15)) }}>
                    <strong>{rule.name}</strong>
                    <small>{rule.measurement_type.replaceAll('_', ' ')} · {rule.operator} {rule.threshold} · {rule.version}</small>
                  </button>
                  <div className="rule-meta">
                    <StatusBadge value={rule.priority} />
                    <StatusBadge value={rule.is_enabled ? 'enabled' : 'disabled'} tone={rule.is_enabled ? 'success' : 'default'} />
                    <button type="button" disabled={busy} onClick={() => void handleToggle(rule, !rule.is_enabled)}>{rule.is_enabled ? 'Disable' : 'Enable'}</button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="detail-panel">
        <div className="detail-panel-heading"><div><p className="page-eyebrow">EVALUATION HISTORY</p><h2>{selectedRule ? `${selectedRule.name} (${selectedRule.version})` : 'Select a rule'}</h2></div></div>
        {!selectedRule ? <EmptyState icon={ArrowUpRight} title="No rule selected" detail="Select a monitoring rule to inspect recent evaluation outcomes." /> : evaluations.length === 0 ? <EmptyState icon={FlaskConical} title="No evaluations yet" detail="Evaluations will appear after accepted measurements are processed." /> : (
          <div className="table-wrap"><table className="data-table"><thead><tr><th>Status</th><th>Incident</th><th>Measurement</th><th>Created</th></tr></thead><tbody>
            {evaluations.map((evaluation) => <tr key={evaluation.id}><td><StatusBadge value={evaluation.status} /></td><td>{evaluation.incident ? evaluation.incident.slice(0, 8) : '—'}</td><td>{evaluation.measurement.slice(0, 8)}</td><td>{new Date(evaluation.created_at).toLocaleString()}</td></tr>)}
          </tbody></table></div>
        )}
      </section>
    </div>
  )
}
