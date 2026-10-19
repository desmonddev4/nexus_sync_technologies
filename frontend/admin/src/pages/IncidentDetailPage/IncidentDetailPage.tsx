import { useCallback, useEffect, useState } from 'react'
import { ArrowLeft, Check, Clock3, Copy, MapPinned, RefreshCw, Route, Send, Truck, Bell, ScrollText } from 'lucide-react'
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

/** The standard response path, in order. Wording matches StatusBadge so nothing implies more than was recorded. */
const LIFECYCLE: { key: string; label: string }[] = [
  { key: 'created', label: 'New' },
  { key: 'acknowledged', label: 'Acknowledged' },
  { key: 'responder_assigned', label: 'Responder assigned' },
  { key: 'dispatch_requested', label: 'Request recorded' },
  { key: 'dispatch_confirmed', label: 'Confirmation recorded' },
  { key: 'responder_en_route', label: 'En route' },
  { key: 'arrived', label: 'Arrived' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'closed', label: 'Closed' },
]

const words = (value: string) => value.replaceAll('_', ' ')
const fmt = (value: string) => new Date(value).toLocaleString()

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
  const [copied, setCopied] = useState(false)

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

  if (loading) {
    return (
      <div className="ui-page" aria-busy="true" aria-label="Loading incident">
        <div className="ui-skeleton" style={{ height: 120 }} />
        <div className="ui-skeleton" style={{ height: 90 }} />
        <div className="ui-skeleton" style={{ height: 300 }} />
      </div>
    )
  }
  if (!incident) return <div className="ui-error" role="alert">{error || 'Incident not found.'}</div>

  const statusActions = nextStatuses[incident.status] || []
  const stepIndex = LIFECYCLE.findIndex((step) => step.key === incident.status)

  async function copyId() {
    try {
      await navigator.clipboard.writeText(incident!.id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch { /* clipboard unavailable */ }
  }

  return (
    <div className="ui-page incident-detail-page">
      <Link to="/incidents" className="back-link"><ArrowLeft size={15} /> Incident queue</Link>

      {/* ---------- Hero ---------- */}
      <header className="id-hero">
        <div className="id-hero__copy">
          <h1>{words(incident.incident_type)}</h1>
          <p>Created {fmt(incident.created_at)} · {incident.trigger_source}</p>
          <button type="button" className={`id-copy${copied ? ' is-copied' : ''}`} onClick={copyId} aria-label="Copy incident identifier">
            <span>#{incident.id.slice(0, 8)}</span>
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <em>{copied ? 'Copied' : 'Copy'}</em>
          </button>
        </div>
        <div className="id-hero__badges"><StatusBadge value={incident.priority} /><StatusBadge value={incident.status} /></div>
      </header>

      {/* ---------- Response path ---------- */}
      {stepIndex >= 0 && (
        <nav className="id-stepper ui-panel" aria-label="Response progress">
          <ol>
            {LIFECYCLE.map((step, index) => (
              <li key={step.key} className={index < stepIndex ? 'is-done' : index === stepIndex ? 'is-current' : undefined} aria-current={index === stepIndex ? 'step' : undefined}>
                <span className="id-step__dot">{index < stepIndex ? <Check size={12} /> : index + 1}</span>
                <span className="id-step__label">{step.label}</span>
              </li>
            ))}
          </ol>
        </nav>
      )}

      {error && <div className="ui-error" role="alert">{error}</div>}

      <div className="incident-detail-grid">
        <div className="incident-main-column">
          {/* ---------- Location ---------- */}
          <section className="ui-panel">
            <div className="ui-panel__head">
              <h2><span className="ui-panel__icon"><MapPinned size={16} /></span> Incident location</h2>
              {incident.location && <StatusBadge value={incident.location.is_stale ? 'stale' : 'current'} tone={incident.location.is_stale ? 'warning' : 'success'} />}
            </div>
            {incident.location ? (
              <div className="id-location">
                <strong className="ui-mono">{incident.location.latitude}, {incident.location.longitude}</strong>
                <p>{incident.location.accuracy_meters ? `Accuracy ±${incident.location.accuracy_meters} m · ` : ''}{fmt(incident.location.recorded_at)}</p>
                <div className="id-chips">
                  <span className="ui-tag">{incident.location.source}</span>
                  <span className="ui-tag">received {fmt(incident.location.received_at)}</span>
                  <span className={`ui-tag${incident.location.is_stale ? ' ui-tag--warn' : ''}`}>{incident.location.age_seconds}s old</span>
                </div>
              </div>
            ) : <p className="ui-muted">No location was available when this incident was created.</p>}
          </section>

          {/* ---------- Coordination ---------- */}
          <section className="ui-panel">
            <div className="ui-panel__head">
              <h2><span className="ui-panel__icon"><Truck size={16} /></span> Responder and dispatch</h2>
              {incident.is_simulated_dispatch && <StatusBadge value="simulated" />}
            </div>

            {incident.assigned_vehicle_identifier ? (
              <div className="id-assignment">
                <span className="id-assignment__icon"><Truck size={20} /></span>
                <div>
                  <strong>{incident.assigned_vehicle_identifier}</strong>
                  <p>{incident.assigned_provider_name} · {incident.assigned_vehicle_source}</p>
                </div>
              </div>
            ) : <p className="ui-muted">No responder assigned.</p>}

            {incident.assigned_vehicle_source === 'simulator' && (
              <div className="ui-notice id-sim">Simulation only. This is not a real ambulance or dispatch.</div>
            )}

            <div className="action-row">
              {incident.status === 'created' && <button type="button" className={`ui-btn${busy ? ' is-busy' : ''}`} disabled={busy} onClick={() => void runAction(() => acknowledgeIncident(incident.id))}><Check size={16} /> Acknowledge</button>}
              {incident.status === 'responder_assigned' && <button type="button" className={`ui-btn${busy ? ' is-busy' : ''}`} disabled={busy} onClick={() => void runAction(() => requestDispatch(incident.id))}><Send size={16} /> Record dispatch request</button>}
              {incident.status === 'dispatch_requested' && (
                <form className="confirmation-form" onSubmit={(event) => { event.preventDefault(); void runAction(() => confirmDispatch(incident.id, confirmationReference)) }}>
                  <label className="ui-field">
                    <input aria-label="Provider confirmation reference" placeholder="Provider call/reference" value={confirmationReference} onChange={(event) => setConfirmationReference(event.target.value)} required />
                  </label>
                  <button type="submit" className={`ui-btn${busy ? ' is-busy' : ''}`} disabled={busy}>Record confirmation</button>
                </form>
              )}
              {statusActions.map((next) => <button key={next} type="button" className={`ui-btn${busy ? ' is-busy' : ''}`} disabled={busy} onClick={() => void runAction(() => advanceIncident(incident.id, next))}>Mark {words(next)}</button>)}
            </div>

            {incident.status === 'responder_assigned' && (
              <div className="vehicle-picker">
                <div className="vehicle-picker-controls">
                  <label className="ui-switch"><input type="checkbox" role="switch" checked={includeSimulated} onChange={(event) => setIncludeSimulated(event.target.checked)} /><span className="ui-switch__track" /><span>Include simulated vehicles</span></label>
                  <button type="button" className="ui-btn ui-btn--soft ui-btn--sm" disabled={busy || !incident.location || incident.location.is_stale} onClick={() => void loadVehicles()}><RefreshCw size={14} /> Find nearby</button>
                </div>
                {!incident.location && <small className="ui-muted">Cannot search: incident has no location snapshot.</small>}
                {incident.location?.is_stale && <small className="ui-muted">Cannot search: patient location is stale.</small>}
                {vehicles.map((vehicle, index) => (
                  <div className="vehicle-option" key={vehicle.id} style={{ animationDelay: `${index * 50}ms` }}>
                    <span className="id-assignment__icon id-assignment__icon--sm"><Truck size={16} /></span>
                    <div>
                      <strong>{vehicle.vehicle_identifier}</strong>
                      <small>{vehicle.provider_name} · {vehicle.distance_kilometers.toFixed(1)} km · updated {vehicle.location_updated_at ? new Date(vehicle.location_updated_at).toLocaleTimeString() : 'unknown'}</small>
                      {vehicle.is_simulated && <StatusBadge value="simulated" />}
                    </div>
                    <button type="button" className="ui-btn ui-btn--sm" disabled={busy} onClick={() => void runAction(() => assignResponder(incident.id, vehicle.id, vehicle.is_simulated))}>Assign</button>
                  </div>
                ))}
              </div>
            )}

            {incident.assigned_vehicle && (
              <div className="route-box">
                <button type="button" className="ui-btn ui-btn--soft" disabled={busy || !incident.location || incident.location.is_stale} onClick={() => void runAction(async () => { setRouteEstimate(await calculateRoute(incident.id)) })}><Route size={16} /> Calculate route / ETA</button>
                {routeEstimate && (
                  <div className="route-result">
                    <div><span>Distance</span><strong>{(routeEstimate.distance_meters / 1000).toFixed(1)} km</strong></div>
                    <div><span>ETA</span><strong>{routeEstimate.duration_minutes} min</strong></div>
                    {routeEstimate.is_simulated && <span className="ui-tag ui-tag--warn">SIMULATED ROUTE</span>}
                  </div>
                )}
              </div>
            )}

            {incident.dispatch_confirmed_at && (
              <p className="confirmation-note"><Clock3 size={14} /> Operator-reported confirmation: {incident.dispatch_confirmation_reference || 'reference not provided'} · {fmt(incident.dispatch_confirmed_at)}</p>
            )}
          </section>

          {/* ---------- Notifications ---------- */}
          <section className="ui-panel">
            <div className="ui-panel__head"><h2><span className="ui-panel__icon"><Bell size={16} /></span> Notification delivery</h2></div>
            {notifications.length === 0 ? (
              <p className="ui-muted">No notifications were queued. Check consent and verified contacts.</p>
            ) : (
              <div className="notification-list">
                {notifications.map((item) => (
                  <div className="notification-row" key={item.id}>
                    <div>
                      <strong>{item.contact_name || 'Emergency contact'}</strong>
                      <small>{item.channel.toUpperCase()} · {item.provider_name || 'Not submitted'}{item.failure_code && ` · ${item.failure_code}`}</small>
                    </div>
                    <StatusBadge value={item.status} />
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* ---------- Audit trail ---------- */}
        <aside className="incident-timeline ui-panel">
          <div className="ui-panel__head"><h2><span className="ui-panel__icon"><ScrollText size={16} /></span> Incident events</h2><span className="ui-tag">{events.length}</span></div>
          {events.length === 0 ? <p className="ui-muted">No events recorded.</p> : (
            <ol>
              {events.map((event, index) => (
                <li key={event.id} style={{ animationDelay: `${Math.min(index, 10) * 40}ms` }}>
                  <span className="timeline-dot" />
                  <strong>{words(event.event_type)}</strong>
                  <time>{fmt(event.created_at)}</time>
                  {Object.keys(event.details).length > 0 && (
                    <details><summary>Details</summary><pre>{JSON.stringify(event.details, null, 2)}</pre></details>
                  )}
                </li>
              ))}
            </ol>
          )}
        </aside>
      </div>
    </div>
  )
}