import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, AlertTriangle, ArrowUpRight, BellRing, Clock3, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getIncidents } from '../../api/operations'
import type { Incident } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { MetricTile } from '../../components/MetricTile/MetricTile'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './OverviewPage.css'

/* ------------------------------------------------------------------ */
/* Config & helpers                                                    */
/* ------------------------------------------------------------------ */

const terminalStatuses = new Set(['resolved', 'closed', 'cancelled'])
const REFRESH_MS = 30_000
const QUEUE_LIMIT = 8

type Row = [key: string, count: number]

function countBy<T>(items: T[], pick: (item: T) => string | null | undefined): Row[] {
  const counts = new Map<string, number>()
  for (const item of items) {
    const key = pick(item) || 'unknown'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
}

const label = (value: string) => value.replaceAll('_', ' ')

function timeLabel(date: Date | null) {
  return date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—'
}

/* ------------------------------------------------------------------ */
/* Small presentational pieces                                         */
/* ------------------------------------------------------------------ */

function Breakdown({ title, rows, loading }: { title: string; rows: Row[]; loading: boolean }) {
  const total = rows.reduce((sum, [, count]) => sum + count, 0)
  return (
    <section className="ov-panel ov-breakdown" aria-label={title}>
      <h3>{title}</h3>
      {loading ? (
        <div className="ov-skeleton-stack" aria-hidden="true"><i /><i /><i /></div>
      ) : rows.length === 0 ? (
        <p className="ov-muted">Nothing to show yet.</p>
      ) : (
        <ul>
          {rows.slice(0, 5).map(([key, count]) => (
            <li key={key}>
              <div className="ov-breakdown-row">
                <span>{label(key)}</span>
                <strong>{count}</strong>
              </div>
              <div className="ov-bar"><span style={{ width: `${(count / total) * 100}%` }} /></div>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function OverviewPage() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null)

  const load = useCallback((silent = false) => {
    if (silent) setRefreshing(true)
    return getIncidents()
      .then((data) => {
        setIncidents(data)
        setError('')
        setUpdatedAt(new Date())
      })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => {
        setLoading(false)
        setRefreshing(false)
      })
  }, [])

  // Initial load, then quiet refresh so the control room stays current.
  useEffect(() => {
    load()
    const timer = window.setInterval(() => load(true), REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [load])

  const stats = useMemo(() => {
    const active = incidents.filter((incident) => !terminalStatuses.has(incident.status))
    return {
      active,
      unacknowledged: active.filter((incident) => incident.status === 'created'),
      staleLocations: active.filter((incident) => incident.location?.is_stale || !incident.location),
      simulated: active.filter((incident) => incident.is_simulated_dispatch),
      recent: [...active]
        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
        .slice(0, QUEUE_LIMIT),
      byStatus: countBy(active, (incident) => incident.status),
      byPriority: countBy(active, (incident) => incident.priority),
      byType: countBy(active, (incident) => incident.incident_type),
    }
  }, [incidents])

  const value = (n: number) => (loading ? '—' : n)

  return (
    <div className="overview-page">
      {/* ---------- Header ---------- */}
      <header className="ov-head">
        <div className="ov-head-copy">
          <h1>Operations overview</h1>
          <p>Current incidents, patient context, and response activity.</p>
        </div>
        <div className="ov-head-actions">
          <span className="ov-live"><i /> System online</span>
          <button type="button" className="ov-refresh" onClick={() => load(true)} disabled={refreshing} aria-label="Refresh incidents">
            <RefreshCw size={14} className={refreshing ? 'is-spinning' : undefined} />
            <span>Updated {timeLabel(updatedAt)}</span>
          </button>
        </div>
      </header>

      {error && <div className="page-error" role="alert">Unable to load operations data: {error}</div>}

      {/* ---------- Attention banner ---------- */}
      {!loading && stats.unacknowledged.length > 0 && (
        <Link to="/incidents" className="ov-attention" role="status">
          <BellRing size={18} />
          <span>
            <strong>{stats.unacknowledged.length}</strong>{' '}
            {stats.unacknowledged.length === 1 ? 'incident needs' : 'incidents need'} acknowledgement
          </span>
          <em>Open queue <ArrowUpRight size={14} /></em>
        </Link>
      )}

      {/* ---------- Key numbers ---------- */}
      <section className="overview-metrics" aria-label="Incident metrics">
        <MetricTile label="Active incidents" value={value(stats.active.length)} detail="Not yet closed" icon={Activity} tone="green" />
        <MetricTile label="Needs acknowledgement" value={value(stats.unacknowledged.length)} detail="Requires operator review" icon={BellRing} tone="coral" />
        <MetricTile label="Stale / missing location" value={value(stats.staleLocations.length)} detail="Do not assume current position" icon={AlertTriangle} tone="amber" />
        <MetricTile label="Simulated incidents" value={value(stats.simulated.length)} detail="Not a real dispatch" icon={Clock3} tone="blue" />
      </section>

      {/* ---------- Queue + breakdowns ---------- */}
      <div className="ov-grid">
        <section className="ov-panel ov-queue" aria-label="Recent incidents">
          <div className="section-heading">
            <div>
              <h2>Recent incidents</h2>
              <p className="ov-muted">Newest active incidents first.</p>
            </div>
            <Link to="/incidents" className="text-link">View queue <ArrowUpRight size={15} /></Link>
          </div>

          {loading ? (
            <div className="ov-skeleton-stack ov-skeleton-stack--rows" aria-hidden="true"><i /><i /><i /><i /></div>
          ) : stats.active.length === 0 ? (
            <EmptyState icon={Activity} title="No active incidents" detail="New SOS alerts and rule-triggered incidents will appear here." />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr><th>Incident</th><th>Priority</th><th>Location</th><th>Responder</th><th>Status</th><th /></tr>
                </thead>
                <tbody>
                  {stats.recent.map((incident) => (
                    <tr key={incident.id} className={incident.status === 'created' ? 'ov-row--new' : undefined}>
                      <td>
                        <Link className="incident-link" to={`/incidents/${incident.id}`}>{label(incident.incident_type)}</Link>
                        <small>{new Date(incident.created_at).toLocaleString()}</small>
                      </td>
                      <td><StatusBadge value={incident.priority} /></td>
                      <td>
                        {incident.location ? (
                          <>
                            <span>{incident.location.latitude}, {incident.location.longitude}</span>
                            <small>{incident.location.is_stale ? 'Stale position' : `Updated ${incident.location.age_seconds}s ago`}</small>
                          </>
                        ) : (
                          <StatusBadge value="missing_location" tone="warning" />
                        )}
                      </td>
                      <td>
                        {incident.assigned_vehicle_identifier || 'Unassigned'}
                        {incident.is_simulated_dispatch && <small>Simulation only</small>}
                      </td>
                      <td><StatusBadge value={incident.status} /></td>
                      <td>
                        <Link className="row-open" to={`/incidents/${incident.id}`} aria-label="Open incident">
                          <ArrowUpRight size={16} />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!loading && stats.active.length > QUEUE_LIMIT && (
            <p className="ov-more">Showing {QUEUE_LIMIT} of {stats.active.length} active incidents.</p>
          )}
        </section>

        <aside className="ov-aside" aria-label="Breakdowns">
          <Breakdown title="By status" rows={stats.byStatus} loading={loading} />
          <Breakdown title="By priority" rows={stats.byPriority} loading={loading} />
          <Breakdown title="By incident type" rows={stats.byType} loading={loading} />
        </aside>
      </div>
    </div>
  )
}