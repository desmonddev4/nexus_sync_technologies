import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, MapPinOff, RefreshCw, Search, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getIncidents } from '../../api/operations'
import type { Incident } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './IncidentsPage.css'

const TERMINAL = ['resolved', 'closed', 'cancelled']
const REFRESH_MS = 30_000

type Filter = 'active' | 'all' | 'closed'

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [filter, setFilter] = useState<Filter>('active')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback((silent = false) => {
    if (silent) setRefreshing(true)
    return getIncidents()
      .then((rows) => { setIncidents(rows); setError('') })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => { setLoading(false); setRefreshing(false) })
  }, [])

  useEffect(() => {
    // Initial network loading is an external synchronization; it updates state when the request settles.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
    const timer = window.setInterval(() => load(true), REFRESH_MS)
    return () => window.clearInterval(timer)
  }, [load])

  const counts = useMemo(() => {
    const closed = incidents.filter((incident) => TERMINAL.includes(incident.status)).length
    return { active: incidents.length - closed, closed, all: incidents.length }
  }, [incidents])

  const needle = query.trim().toLowerCase()
  const visible = useMemo(() => incidents
    .filter((incident) => {
      const isTerminal = TERMINAL.includes(incident.status)
      if (filter === 'active' && isTerminal) return false
      if (filter === 'closed' && !isTerminal) return false
      const text = `${incident.id} ${incident.incident_type} ${incident.status} ${incident.trigger_source} ${incident.assigned_vehicle_identifier || ''}`.toLowerCase()
      return text.includes(needle)
    })
    .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)),
  [incidents, filter, needle])

  const tabs: { key: Filter; label: string }[] = [
    { key: 'active', label: 'Active' },
    { key: 'all', label: 'All' },
    { key: 'closed', label: 'Closed' },
  ]

  return (
    <div className="ui-page incidents-page">
      <header className="ui-head">
        <div>
          <h1>Incident queue</h1>
          <p>Review alerts and coordinate only from verified information.</p>
        </div>
        <div className="ui-head__aside">
          <span className="ui-pill"><strong>{visible.length}</strong> records</span>
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => load(true)} disabled={refreshing} aria-label="Refresh incidents">
            <RefreshCw size={14} className={refreshing ? 'is-spinning' : undefined} /> Refresh
          </button>
        </div>
      </header>

      <section className="ui-toolbar" aria-label="Incident filters">
        <div className="ui-search">
          <Search size={17} />
          <input aria-label="Search incidents" placeholder="Search incident, trigger, responder…" value={query} onChange={(event) => setQuery(event.target.value)} />
          {query && <button type="button" className="ui-search__clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}
        </div>
        <div className="ui-segment" role="group" aria-label="Filter incident status">
          {tabs.map(({ key, label }) => (
            <button key={key} type="button" className={filter === key ? 'is-on' : undefined} onClick={() => setFilter(key)} aria-pressed={filter === key}>
              {label} <em>{counts[key]}</em>
            </button>
          ))}
        </div>
      </section>

      {error && <div className="ui-error" role="alert">Unable to load incidents: {error}</div>}

      {loading ? (
        <div className="ui-skeleton-stack" aria-busy="true"><div className="ui-skeleton" /><div className="ui-skeleton" /><div className="ui-skeleton" /><div className="ui-skeleton" /></div>
      ) : visible.length === 0 ? (
        <section className="ui-panel inc-empty">
          <EmptyState icon={Search} title="No matching incidents" detail="Try another filter or search term." />
          {(query || filter !== 'all') && (
            <button type="button" className="ui-btn ui-btn--sm" onClick={() => { setQuery(''); setFilter('all') }}>Show all incidents</button>
          )}
        </section>
      ) : (
        <section className="ui-panel ui-table-wrap">
          <table className="data-table ui-table">
            <thead>
              <tr><th>Incident</th><th>Patient position</th><th>Priority</th><th>Responder</th><th>Status</th><th>Created</th><th /></tr>
            </thead>
            <tbody>
              {visible.map((incident, index) => (
                <tr key={incident.id} className={incident.status === 'created' ? 'inc-row--new' : undefined} style={{ animationDelay: `${Math.min(index, 10) * 30}ms` }}>
                  <td>
                    <Link to={`/incidents/${incident.id}`} className="ui-link">{incident.incident_type.replaceAll('_', ' ')}</Link>
                    <small>#{incident.id.slice(0, 8)} · {incident.trigger_source}</small>
                  </td>
                  <td>
                    {incident.location ? (
                      <>
                        <span className="ui-mono inc-coords">{incident.location.latitude}, {incident.location.longitude}</span>
                        {incident.location.is_stale
                          ? <small><span className="ui-tag ui-tag--warn">STALE LOCATION</span></small>
                          : <small>Last update {incident.location.age_seconds}s ago</small>}
                      </>
                    ) : (
                      <StatusBadge value="missing_location" tone="warning" />
                    )}
                  </td>
                  <td><StatusBadge value={incident.priority} /></td>
                  <td>
                    {incident.assigned_vehicle_identifier || <span className="inc-unassigned"><MapPinOff size={13} /> Unassigned</span>}
                    {incident.is_simulated_dispatch && <small><span className="ui-tag ui-tag--warn">SIMULATED ONLY</span></small>}
                  </td>
                  <td><StatusBadge value={incident.status} /></td>
                  <td>{new Date(incident.created_at).toLocaleString()}</td>
                  <td><Link to={`/incidents/${incident.id}`} className="ui-open" aria-label="Open incident"><ArrowUpRight size={15} /></Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  )
}