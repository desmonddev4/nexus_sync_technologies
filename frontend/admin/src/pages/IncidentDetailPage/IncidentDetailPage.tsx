import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Check, MapPinned, RefreshCw, Send, Truck } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { acknowledgeIncident, advanceIncident, assignResponder, calculateRoute, confirmDispatch, getIncident, getIncidentEvents, getIncidentNotifications, getNearbyVehicles, requestDispatch } from '../../api/operations'
import type { Incident, IncidentEvent, IncidentNotification, NearbyVehicle } from '../../types/api'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './IncidentDetailPage.css'

const nextStatuses: Partial<Record<Incident['status'], Incident['status'][]>> = {
  dispatch_confirmed: ['responder_en_route'],
  responder_en_route: ['arrived'],
  arrived: ['resolved'],
  resolved: ['closed'],
}

export function IncidentDetailPage() {
  const { incidentId = '' } = useParams()
  const [incident, setIncident] = useState<Incident | null>(null)
  const [events, setEvents] = useState<IncidentEvent[]>([])
  const [notifications, setNotifications] = useState<IncidentNotification[]>([])
  const [vehicles, setVehicles] = useState<NearbyVehicle[]>([])
  const [includeSimulated, setIncludeSimulated] = useState(false)
  const [confirmationReference, setConfirmationReference] = useState('')
  const [routeEstimate, setRouteEstimate] = useState<{ distance_meters: number; duration_minutes: number; is_simulated: boolean } | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    const [currentIncident, currentEvents, currentNotifications] = await Promise.all([
      getIncident(incidentId), getIncidentEvents(incidentId), getIncidentNotifications(incidentId),
    ])
    setIncident(currentIncident)
    setEvents(currentEvents)
    setNotifications(currentNotifications)
  }, [incidentId])

  useEffect(() => {
    let active = true
    Promise.all([getIncident(incidentId), getIncidentEvents(incidentId), getIncidentNotifications(incidentId)])
      .then(([currentIncident, currentEvents, currentNotifications]) => {
        if (!active) return
        setIncident(currentIncident)
        setEvents(currentEvents)
        setNotifications(currentNotifications)
      })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [incidentId])

  async function runAction(action: () => Promise<unknown>) {
    setError('')
    setBusy(true)
    try { await action(); await refresh() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'The operation could not be completed.') }
    finally { setBusy(false) }
  }

  async function loadVehicles() {
    if (!incident?.location) return
    setBusy(true)
    setError('')
    try {
      setVehicles(await getNearbyVehicles(incident.location.latitude, incident.location.longitude, includeSimulated))
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to find eligible vehicles.') }
    finally { setBusy(false) }
  }

  if (loading) return <div className="incident-detail-loading">Loading incident…</div>
  if (!incident) return <div className="page-error" role="alert">{error || 'Incident not found.'}</div>
  const statusActions = nextStatuses[incident.status] || []

  return (
    <div className="incident-detail-page">
      <Link to="/incidents" className="back-link"><ArrowLeft size={15} /> Incident queue</Link>
      <header className="incident-detail-heading">
        <div><p className="page-eyebrow">INCIDENT / {incident.id.slice(0, 8).toUpperCase()}</p><h1>{incident.incident_type.replaceAll('_', ' ')}</h1><p className="page-subtitle">Created {new Date(incident.created_at).toLocaleString()} · {incident.trigger_source}</p></div>
        <div className="incident-heading-status"><StatusBadge value={incident.priority} /><StatusBadge value={incident.status} /></div>
      </header>
      {error && <div className="page-error" role="alert">{error}</div>}

      <div className="incident-detail-grid">
        <div className="incident-main-column">
          <section className="detail-panel">
            <div className="detail-panel-heading"><div><p className="page-eyebrow">PATIENT POSITION</p><h2>Incident location</h2></div>{incident.location && <StatusBadge value={incident.location.is_stale ? 'stale' : 'current'} tone={incident.location.is_stale ? 'warning' : 'success'} />}</div>
            {incident.location ? <div className="location-summary"><MapPinned size={19} /><div><strong>{incident.location.latitude}, {incident.location.longitude}</strong><p>{incident.location.accuracy_meters ? `Accuracy ±${incident.location.accuracy_meters} m · ` : ''}{new Date(incident.location.recorded_at).toLocaleString()}</p><small>{incident.location.source} · received {new Date(incident.location.received_at).toLocaleString()} · {incident.location.age_seconds}s old</small></div></div> : <p className="detail-empty">No location was available when this incident was created.</p>}
          </section>

          <section className="detail-panel">
            <div className="detail-panel-heading"><div><p className="page-eyebrow">COORDINATION</p><h2>Responder and dispatch</h2></div>{incident.is_simulated_dispatch && <StatusBadge value="simulated" />}</div>
            {incident.assigned_vehicle_identifier ? <div className="assignment-summary"><Truck size={18} /><div><strong>{incident.assigned_vehicle_identifier}</strong><p>{incident.assigned_provider_name} · {incident.assigned_vehicle_source}</p></div></div> : <p className="detail-empty">No responder assigned.</p>}
            {incident.assigned_vehicle_source === 'simulator' && <div className="simulation-notice">Simulation only. This is not a real ambulance or dispatch.</div>}
            <div className="action-row">
              {incident.status === 'created' && <button type="button" disabled={busy} onClick={() => void runAction(() => acknowledgeIncident(incident.id))}><Check size={15} /> Acknowledge</button>}
              {incident.status === 'responder_assigned' && <button type="button" disabled={busy} onClick={() => void runAction(() => requestDispatch(incident.id))}><Send size={15} /> Record dispatch request</button>}
              {incident.status === 'dispatch_requested' && <form className="confirmation-form" onSubmit={(event) => { event.preventDefault(); void runAction(() => confirmDispatch(incident.id, confirmationReference)) }}><input aria-label="Provider confirmation reference" placeholder="Provider call/reference" value={confirmationReference} onChange={(event) => setConfirmationReference(event.target.value)} required /><button type="submit" disabled={busy}>Record confirmation</button></form>}
              {statusActions.map((next) => <button key={next} type="button" disabled={busy} onClick={() => void runAction(() => advanceIncident(incident.id, next))}>Mark {next.replaceAll('_', ' ')}</button>)}
            </div>
            {incident.status === 'responder_assigned' && <div className="vehicle-picker">
              <div className="vehicle-picker-controls"><label><input type="checkbox" checked={includeSimulated} onChange={(event) => setIncludeSimulated(event.target.checked)} /> Include simulated vehicles</label><button type="button" disabled={busy || !incident.location || incident.location.is_stale} onClick={() => void loadVehicles()}><RefreshCw size={14} /> Find nearby</button></div>
              {!incident.location && <small>Cannot search: incident has no location snapshot.</small>}
              {incident.location?.is_stale && <small>Cannot search: patient location is stale.</small>}
              {vehicles.map((vehicle) => <div className="vehicle-option" key={vehicle.id}><div><strong>{vehicle.vehicle_identifier}</strong><small>{vehicle.provider_name} · {vehicle.distance_kilometers.toFixed(1)} km · updated {vehicle.location_updated_at ? new Date(vehicle.location_updated_at).toLocaleTimeString() : 'unknown'}</small>{vehicle.is_simulated && <StatusBadge value="simulated" />}</div><button type="button" disabled={busy} onClick={() => void runAction(() => assignResponder(incident.id, vehicle.id, vehicle.is_simulated))}>Assign</button></div>)}
            </div>}
            {incident.assigned_vehicle && <div className="route-box"><button type="button" disabled={busy || !incident.location || incident.location.is_stale} onClick={() => void runAction(async () => { setRouteEstimate(await calculateRoute(incident.id)) })}><MapPinned size={15} /> Calculate route / ETA</button>{routeEstimate && <p>{(routeEstimate.distance_meters / 1000).toFixed(1)} km · {routeEstimate.duration_minutes} min {routeEstimate.is_simulated && '· SIMULATED ROUTE'}</p>}</div>}
            {incident.dispatch_confirmed_at && <p className="confirmation-note">Operator-reported confirmation: {incident.dispatch_confirmation_reference || 'reference not provided'} · {new Date(incident.dispatch_confirmed_at).toLocaleString()}</p>}
          </section>

          <section className="detail-panel"><div className="detail-panel-heading"><div><p className="page-eyebrow">CONTACT ALERTS</p><h2>Notification delivery</h2></div></div>
            {notifications.length === 0 ? <p className="detail-empty">No notifications were queued. Check consent and verified contacts.</p> : <div className="notification-list">{notifications.map((item) => <div className="notification-row" key={item.id}><div><strong>{item.contact_name || 'Emergency contact'}</strong><small>{item.channel.toUpperCase()} · {item.provider_name || 'Not submitted'}{item.failure_code && ` · ${item.failure_code}`}</small></div><StatusBadge value={item.status} /></div>)}</div>}
          </section>
        </div>

        <aside className="incident-timeline detail-panel"><p className="page-eyebrow">AUDIT TRAIL</p><h2>Incident events</h2>{events.length === 0 ? <p className="detail-empty">No events recorded.</p> : <ol>{events.map((event) => <li key={event.id}><span className="timeline-dot" /><strong>{event.event_type.replaceAll('_', ' ')}</strong><time>{new Date(event.created_at).toLocaleString()}</time>{Object.keys(event.details).length > 0 && <pre>{JSON.stringify(event.details, null, 2)}</pre>}</li>)}</ol>}</aside>
      </div>
    </div>
  )
}