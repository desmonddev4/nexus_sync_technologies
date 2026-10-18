import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, Search } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getIncidents } from '../../api/operations'
import type { Incident } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './IncidentsPage.css'

export function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [filter, setFilter] = useState('active')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getIncidents().then(setIncidents).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false))
  }, [])

  const visible = useMemo(() => incidents.filter((incident) => {
    const isTerminal = ['resolved', 'closed', 'cancelled'].includes(incident.status)
    if (filter === 'active' && isTerminal) return false
    if (filter === 'closed' && !isTerminal) return false
    const text = `${incident.id} ${incident.incident_type} ${incident.status} ${incident.assigned_vehicle_identifier || ''}`.toLowerCase()
    return text.includes(query.toLowerCase())
  }), [incidents, filter, query])

  return (
    <div className="incidents-page">
      <header className="page-heading"><div><p className="page-eyebrow">OPERATIONS / INCIDENTS</p><h1>Incident queue</h1><p className="page-subtitle">Review alerts and coordinate only from verified information.</p></div><span className="incidents-count">{visible.length} records</span></header>
      <section className="incident-controls" aria-label="Incident filters">
        <div className="incident-search"><Search size={16} /><input aria-label="Search incidents" placeholder="Search incident, trigger, responder…" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
        <div className="incident-filter" role="group" aria-label="Filter incident status">
          <button type="button" className={filter === 'active' ? 'is-active' : ''} onClick={() => setFilter('active')}>Active</button>
          <button type="button" className={filter === 'all' ? 'is-active' : ''} onClick={() => setFilter('all')}>All</button>
          <button type="button" className={filter === 'closed' ? 'is-active' : ''} onClick={() => setFilter('closed')}>Closed</button>
        </div>
      </section>
      {error && <div className="page-error" role="alert">Unable to load incidents: {error}</div>}
      {loading ? <div className="loading-row">Loading incident records…</div> : visible.length === 0 ? <EmptyState icon={Search} title="No matching incidents" detail="Try another filter or search term." /> : (
        <div className="table-wrap incident-table-wrap"><table className="data-table"><thead><tr><th>Incident</th><th>Patient position</th><th>Priority</th><th>Responder</th><th>Status</th><th>Created</th><th /></tr></thead><tbody>
          {visible.map((incident) => <tr key={incident.id}>
            <td><Link to={`/incidents/${incident.id}`} className="incident-link">{incident.incident_type.replaceAll('_', ' ')}</Link><small>#{incident.id.slice(0, 8)} · {incident.trigger_source}</small></td>
            <td>{incident.location ? <><span>{incident.location.latitude}, {incident.location.longitude}</span><small>{incident.location.is_stale ? 'STALE LOCATION' : `Last update ${incident.location.age_seconds}s ago`}</small></> : <StatusBadge value="missing_location" tone="warning" />}</td>
            <td><StatusBadge value={incident.priority} /></td>
            <td>{incident.assigned_vehicle_identifier || 'Unassigned'}{incident.is_simulated_dispatch && <small>SIMULATED ONLY</small>}</td>
            <td><StatusBadge value={incident.status} /></td>
            <td>{new Date(incident.created_at).toLocaleString()}</td>
            <td><Link to={`/incidents/${incident.id}`} className="row-open" aria-label="Open incident"><ArrowUpRight size={15} /></Link></td>
          </tr>)}
        </tbody></table></div>
      )}
    </div>
  )
}