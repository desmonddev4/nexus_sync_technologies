import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Filter, RotateCcw, ShieldCheck } from 'lucide-react'
import { getAuditLogs } from '../../api/operations'
import type { AuditLogEntry } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './AuditLogsPage.css'

interface AuditFilters {
  actor: string
  action: string
  resource: string
  outcome: '' | 'success' | 'denied' | 'failure'
  start_date: string
  end_date: string
}

const DEFAULT_FILTERS: AuditFilters = {
  actor: '',
  action: '',
  resource: '',
  outcome: '',
  start_date: '',
  end_date: '',
}

const OUTCOMES: { value: AuditFilters['outcome']; label: string }[] = [
  { value: '', label: 'Any' },
  { value: 'success', label: 'Success' },
  { value: 'denied', label: 'Denied' },
  { value: 'failure', label: 'Failure' },
]

export function AuditLogsPage() {
  const [entries, setEntries] = useState<AuditLogEntry[]>([])
  const [filters, setFilters] = useState<AuditFilters>(DEFAULT_FILTERS)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(currentFilters: AuditFilters) {
    setError('')
    const result = await getAuditLogs({ ...currentFilters, limit: 200 })
    setEntries(result)
  }

  useEffect(() => {
    let active = true
    const timer = window.setTimeout(() => {
      load(DEFAULT_FILTERS)
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

  async function handleApply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setLoading(true)
    try {
      await load(filters)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load audit logs.')
    } finally {
      setLoading(false)
    }
  }

  async function handleReset() {
    setFilters(DEFAULT_FILTERS)
    setLoading(true)
    try {
      await load(DEFAULT_FILTERS)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load audit logs.')
    } finally {
      setLoading(false)
    }
  }

  const activeFilterCount = Object.values(filters).filter(Boolean).length

  return (
    <div className="ui-page audit-page">
      <header className="ui-head">
        <div>
          <h1>Audit log viewer</h1>
          <p>Filter actions by actor, action, resource, date, and outcome.</p>
        </div>
        <span className="ui-pill"><strong>{entries.length}</strong> events</span>
      </header>

      <form className="ui-panel audit-filters" onSubmit={handleApply}>
        <label className="ui-field">Actor<input value={filters.actor} onChange={(event) => setFilters({ ...filters, actor: event.target.value })} placeholder="username or user id" /></label>
        <label className="ui-field">Action<input value={filters.action} onChange={(event) => setFilters({ ...filters, action: event.target.value })} placeholder="incident.read" /></label>
        <label className="ui-field">Resource<input value={filters.resource} onChange={(event) => setFilters({ ...filters, resource: event.target.value })} placeholder="incident" /></label>
        <label className="ui-field">Start date<input type="date" value={filters.start_date} onChange={(event) => setFilters({ ...filters, start_date: event.target.value })} /></label>
        <label className="ui-field">End date<input type="date" value={filters.end_date} onChange={(event) => setFilters({ ...filters, end_date: event.target.value })} /></label>

        <div className="ui-field audit-outcome">
          <span>Outcome</span>
          <div className="ui-segment" role="group" aria-label="Outcome">
            {OUTCOMES.map(({ value, label }) => (
              <button key={label} type="button" className={filters.outcome === value ? 'is-on' : undefined} onClick={() => setFilters({ ...filters, outcome: value })} aria-pressed={filters.outcome === value}>{label}</button>
            ))}
          </div>
        </div>

        <div className="audit-filter-actions">
          <button type="submit" className={`ui-btn${loading ? ' is-busy' : ''}`} disabled={loading}><Filter size={15} /> Apply filters{activeFilterCount > 0 && <span className="audit-badge">{activeFilterCount}</span>}</button>
          <button type="button" className="ui-btn ui-btn--ghost" onClick={() => void handleReset()}><RotateCcw size={14} /> Reset</button>
        </div>
      </form>

      {error && <div className="ui-error" role="alert">{error}</div>}

      <section className="ui-panel">
        <div className="ui-panel__head">
          <h2><span className="ui-panel__icon"><ShieldCheck size={16} /></span> Audit events</h2>
        </div>
        {loading ? (
          <div className="ui-skeleton-stack" aria-busy="true"><div className="ui-skeleton" /><div className="ui-skeleton" /><div className="ui-skeleton" /></div>
        ) : entries.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No matching audit events" detail="Try broadening your filters or date range." />
        ) : (
          <div className="ui-table-wrap">
            <table className="data-table ui-table">
              <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Outcome</th><th>Request</th></tr></thead>
              <tbody>
                {entries.map((entry, index) => (
                  <tr key={entry.id} className={`audit-row audit-row--${entry.outcome}`} style={{ animationDelay: `${Math.min(index, 10) * 25}ms` }}>
                    <td>{new Date(entry.created_at).toLocaleString()}</td>
                    <td>{entry.actor_username || <span className="ui-tag">system</span>}</td>
                    <td><code className="audit-code">{entry.action}</code></td>
                    <td>{entry.resource_type}{entry.resource_id ? <small className="ui-mono">{entry.resource_id}</small> : null}</td>
                    <td><StatusBadge value={entry.outcome} tone={entry.outcome === 'denied' ? 'warning' : entry.outcome === 'failure' ? 'danger' : 'success'} /></td>
                    <td>
                      {entry.http_method ? <span className={`audit-method audit-method--${entry.http_method.toLowerCase()}`}>{entry.http_method}</span> : '—'}
                      {entry.request_id ? <small className="request-id ui-mono">ID {entry.request_id}</small> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  )
}