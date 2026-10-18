import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Filter, ShieldCheck } from 'lucide-react'
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

  return (
    <div className="audit-page">
      <header className="page-heading">
        <div>
          <p className="page-eyebrow">OPERATIONS / AUDIT</p>
          <h1>Audit log viewer</h1>
          <p className="page-subtitle">Filter actions by actor, action, resource, date, and outcome.</p>
        </div>
        <span className="audit-count">{entries.length} events</span>
      </header>

      <form className="audit-filters" onSubmit={handleApply}>
        <label>Actor<input value={filters.actor} onChange={(event) => setFilters({ ...filters, actor: event.target.value })} placeholder="username or user id" /></label>
        <label>Action<input value={filters.action} onChange={(event) => setFilters({ ...filters, action: event.target.value })} placeholder="incident.read" /></label>
        <label>Resource<input value={filters.resource} onChange={(event) => setFilters({ ...filters, resource: event.target.value })} placeholder="incident" /></label>
        <label>Outcome<select value={filters.outcome} onChange={(event) => setFilters({ ...filters, outcome: event.target.value as AuditFilters['outcome'] })}><option value="">Any</option><option value="success">Success</option><option value="denied">Denied</option><option value="failure">Failure</option></select></label>
        <label>Start date<input type="date" value={filters.start_date} onChange={(event) => setFilters({ ...filters, start_date: event.target.value })} /></label>
        <label>End date<input type="date" value={filters.end_date} onChange={(event) => setFilters({ ...filters, end_date: event.target.value })} /></label>
        <div className="audit-filter-actions">
          <button type="submit"><Filter size={15} /> Apply filters</button>
          <button type="button" className="secondary" onClick={() => void handleReset()}>Reset</button>
        </div>
      </form>

      {error && <div className="page-error" role="alert">{error}</div>}

      <section className="detail-panel">
        <div className="detail-panel-heading"><div><p className="page-eyebrow">EVENT STREAM</p><h2>Audit events</h2></div></div>
        {loading ? <div className="loading-row">Loading audit events…</div> : entries.length === 0 ? (
          <EmptyState icon={ShieldCheck} title="No matching audit events" detail="Try broadening your filters or date range." />
        ) : (
          <div className="table-wrap"><table className="data-table"><thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th><th>Outcome</th><th>Request</th></tr></thead><tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{new Date(entry.created_at).toLocaleString()}</td>
                <td>{entry.actor_username || 'system'}</td>
                <td>{entry.action}</td>
                <td>{entry.resource_type}{entry.resource_id ? `:${entry.resource_id}` : ''}</td>
                <td><StatusBadge value={entry.outcome} tone={entry.outcome === 'denied' ? 'warning' : entry.outcome === 'failure' ? 'danger' : 'success'} /></td>
                <td>{entry.http_method || '—'}{entry.request_id ? <small className="request-id">ID {entry.request_id}</small> : null}</td>
              </tr>
            ))}
          </tbody></table></div>
        )}
      </section>
    </div>
  )
}
