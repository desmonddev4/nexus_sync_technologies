import { useEffect, useState } from 'react'
import { Activity, AlertTriangle, BellRing, Clock3, ArrowUpRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getIncidents } from '../../api/operations'
import type { Incident } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { MetricTile } from '../../components/MetricTile/MetricTile'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './OverviewPage.css'

const terminalStatuses = new Set(['resolved', 'closed', 'cancelled'])

export function OverviewPage() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getIncidents()
      .then(setIncidents)
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  const active = incidents.filter((incident) => !terminalStatuses.has(incident.status))
  const unacknowledged = active.filter((incident) => incident.status === 'created')
  const staleLocations = active.filter((incident) => incident.location?.is_stale || !incident.location)

  return (
    <div className="overview-page">
      <header className="page-heading">
        <div><p className="page-eyebrow">CONTROL ROOM / LIVE OPERATIONS</p><h1>Operations overview</h1><p className="page-subtitle">Current incidents, patient context, and response activity.</p></div>
        <span className="overview-live"><i /> SYSTEM ONLINE</span>
      </header>

      {error && <div className="page-error" role="alert">Unable to load operations data: {error}</div>}

      <section className="overview-metrics" aria-label="Incident metrics">
        <MetricTile label="Active incidents" value={loading ? '—' : active.length} detail="Not yet closed" icon={Activity} tone="green" />
        <MetricTile label="Needs acknowledgement" value={loading ? '—' : unacknowledged.length} detail="Requires operator review" icon={BellRing} tone="coral" />
        <MetricTile label="Stale / missing location" value={loading ? '—' : staleLocations.length} detail="Do not assume current position" icon={AlertTriangle} tone="amber" />
        <MetricTile label="Simulated incidents" value={loading ? '—' : active.filter((item) => item.is_simulated_dispatch).length} detail="Not a real dispatch" icon={Clock3} tone="blue" />
      </section>

      <section className="overview-section">
        <div className="section-heading"><div><p className="page-eyebrow">RESPONSE QUEUE</p><h2>Recent incidents</h2></div><Link to="/incidents" className="text-link">View queue <ArrowUpRight size={15} /></Link></div>
        {loading ? <div className="loading-row">Loading incident data…</div> : active.length === 0 ? (
          <EmptyState icon={Activity} title="No active incidents" detail="New SOS alerts and rule-triggered incidents will appear here." />
        ) : (
          <div className="table-wrap"><table className="data-table"><thead><tr><th>Incident</th><th>Priority</th><th>Location</th><th>Responder</th><th>Status</th><th /></tr></thead>
            <tbody>{active.slice(0, 8).map((incident) => <tr key={incident.id}>
              <td><Link className="incident-link" to={`/incidents/${incident.id}`}>{incident.incident_type.replaceAll('_', ' ')}</Link><small>{new Date(incident.created_at).toLocaleString()}</small></td>
              <td><StatusBadge value={incident.priority} /></td>
              <td>{incident.location ? <><span>{incident.location.latitude}, {incident.location.longitude}</span><small>{incident.location.is_stale ? 'Stale position' : `Updated ${incident.location.age_seconds}s ago`}</small></> : <StatusBadge value="missing_location" tone="warning" />}</td>
              <td>{incident.assigned_vehicle_identifier || 'Unassigned'}{incident.is_simulated_dispatch && <small>Simulation only</small>}</td>
              <td><StatusBadge value={incident.status} /></td>
              <td><Link className="row-open" to={`/incidents/${incident.id}`} aria-label="Open incident"><ArrowUpRight size={16} /></Link></td>
            </tr>)}</tbody></table></div>
        )}
      </section>
    </div>
  )
}