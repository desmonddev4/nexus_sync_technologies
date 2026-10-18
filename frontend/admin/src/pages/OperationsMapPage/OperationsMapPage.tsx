import { useCallback, useEffect, useState } from 'react'
import { MapContainer, Marker, Polyline, Popup, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import { divIcon } from 'leaflet'
import type { DivIcon } from 'leaflet'
import { Link } from 'react-router-dom'
import {
  Activity,
  Ambulance,
  ArrowUpRight,
  Building2,
  Crosshair,
  Maximize,
  MapPinOff,
  Moon,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  Route as RouteIcon,
  Siren,
  Sun,
  Truck,
} from 'lucide-react'
import { calculateRoute, getFacilities, getIncidents, getNearbyVehicles, getProviders } from '../../api/operations'
import type { EmergencyProvider, HealthcareFacility, Incident, NearbyVehicle } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './OperationsMapPage.css'

/* ------------------------------------------------------------------ */
/* Constants & small helpers                                           */
/* ------------------------------------------------------------------ */

const UPSA_CENTER: [number, number] = [5.6508, -0.1869]
const TERMINAL_STATUSES = new Set(['resolved', 'closed', 'cancelled'])
const STALE_AFTER_MS = 300_000
const PANEL_WIDTH = 372

type Point = [number, number]
type LayerKey = 'incidents' | 'facilities' | 'providers' | 'vehicles'
type Basemap = 'dark' | 'light'

const BASEMAPS: Record<Basemap, { label: string; url: string; attribution: string }> = {
  dark: {
    label: 'Dark',
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
  },
  light: {
    label: 'Light',
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  },
}

function parsePoint(latitude?: string | null, longitude?: string | null): Point | null {
  if (!latitude || !longitude) return null
  const lat = Number(latitude)
  const lng = Number(longitude)
  return Number.isFinite(lat) && Number.isFinite(lng) && Math.abs(lat) <= 90 && Math.abs(lng) <= 180
    ? [lat, lng]
    : null
}

function decodePolyline(encoded: string): Point[] {
  const points: Point[] = []
  let index = 0
  let latitude = 0
  let longitude = 0
  while (index < encoded.length) {
    let result = 0
    let shift = 0
    let byte: number
    do {
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20 && index < encoded.length)
    latitude += (result & 1) ? ~(result >> 1) : (result >> 1)

    result = 0
    shift = 0
    do {
      byte = encoded.charCodeAt(index++) - 63
      result |= (byte & 0x1f) << shift
      shift += 5
    } while (byte >= 0x20 && index < encoded.length)
    longitude += (result & 1) ? ~(result >> 1) : (result >> 1)
    points.push([latitude / 1e5, longitude / 1e5])
  }
  return points
}

function relativeAge(seconds: number) {
  if (seconds < 60) return `${seconds}s ago`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  return `${Math.floor(seconds / 3600)}h ago`
}

const words = (value: string) => value.replaceAll('_', ' ')
const signature = (points: Point[]) => points.map((point) => point.join(',')).join('|')

/* ------------------------------------------------------------------ */
/* Marker icons — HTML markers with radar pulses (cached so the CSS    */
/* animations don't restart on every re-render)                        */
/* ------------------------------------------------------------------ */

type MarkerKind = 'incident' | 'facility' | 'provider' | 'vehicle'
const iconCache = new Map<string, DivIcon>()

function markerIcon(kind: MarkerKind, flags: { stale?: boolean; selected?: boolean; simulated?: boolean } = {}) {
  const classes = ['mk', `mk--${kind}`, flags.stale && 'is-stale', flags.selected && 'is-selected', flags.simulated && 'is-sim']
    .filter(Boolean)
    .join(' ')
  let icon = iconCache.get(classes)
  if (!icon) {
    icon = divIcon({
      className: 'mk-wrap',
      html: `<span class="${classes}"><i class="mk-ring"></i><i class="mk-ring mk-ring--late"></i><b class="mk-core"></b></span>`,
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -18],
    })
    iconCache.set(classes, icon)
  }
  return icon
}

/* ------------------------------------------------------------------ */
/* Camera helpers                                                      */
/* ------------------------------------------------------------------ */

/** Frames every incident, facility and station. Re-runs only when the set of points changes or "Reset view" is pressed. */
function FitMap({ points, nonce, rightPad }: { points: Point[]; nonce: number; rightPad: number }) {
  const map = useMap()
  const sig = signature(points)

  useEffect(() => {
    const options = { paddingTopLeft: [48, 96] as [number, number], paddingBottomRight: [rightPad, 84] as [number, number], maxZoom: 14 }
    if (points.length === 1) map.setView(points[0], 13)
    else if (points.length > 1) map.fitBounds(points, options)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, sig, nonce])
  return null
}

/** Glides to the incident the operator picked, then widens to include any responders that load for it. */
function FocusIncident({ target, vehicles, nonce, rightPad }: { target: Point | null; vehicles: Point[]; nonce: number; rightPad: number }) {
  const map = useMap()
  const vehicleSig = signature(vehicles)

  useEffect(() => {
    if (!target || nonce === 0) return
    map.flyToBounds([target, ...vehicles], {
      paddingTopLeft: [60, 100],
      paddingBottomRight: [rightPad, 90],
      maxZoom: 14,
      duration: 0.9,
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, target?.[0], target?.[1], vehicleSig, nonce])
  return null
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function OperationsMapPage() {
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [facilities, setFacilities] = useState<HealthcareFacility[]>([])
  const [providers, setProviders] = useState<EmergencyProvider[]>([])
  const [vehicleResult, setVehicleResult] = useState<{ incidentId: string; vehicles: NearbyVehicle[] } | null>(null)
  const [selectedIncidentId, setSelectedIncidentId] = useState('')
  const [includeSimulation, setIncludeSimulation] = useState(true)
  const [routeResult, setRouteResult] = useState<{ incidentId: string; points: Point[]; notice: string } | null>(null)
  const [routing, setRouting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [now, setNow] = useState(() => Date.now())

  // Presentation state
  const [basemap, setBasemap] = useState<Basemap>('dark')
  const [panelOpen, setPanelOpen] = useState(true)
  const [layers, setLayers] = useState<Record<LayerKey, boolean>>({ incidents: true, facilities: true, providers: true, vehicles: true })
  const [focusNonce, setFocusNonce] = useState(0)
  const [fitNonce, setFitNonce] = useState(0)

  const isStale = (location: { is_stale?: boolean; recorded_at: string }) =>
    Boolean(location.is_stale) || now - Date.parse(location.recorded_at) > STALE_AFTER_MS
  const ageOf = (recordedAt: string) => relativeAge(Math.max(0, Math.floor((now - Date.parse(recordedAt)) / 1000)))

  const selectedIncident = incidents.find((incident) => incident.id === selectedIncidentId) || null
  const activeIncidents = incidents.filter((incident) => !TERMINAL_STATUSES.has(incident.status))
  const locatedIncidents = activeIncidents.filter((incident) => incident.location)
  const selectedLocation = selectedIncident?.location
  const selectedLocationStale = Boolean(selectedLocation?.is_stale)
    || Boolean(selectedLocation && now - Date.parse(selectedLocation.recorded_at) > STALE_AFTER_MS)
  const displayedVehicles = (
    vehicleResult?.incidentId === selectedIncidentId && selectedLocation && !selectedLocationStale
      ? vehicleResult.vehicles.filter((vehicle) => includeSimulation || !vehicle.is_simulated)
      : []
  )
  const visibleRoute = routeResult?.incidentId === selectedIncidentId ? routeResult : null

  const incidentPoints = locatedIncidents
    .map((incident) => parsePoint(incident.location?.latitude, incident.location?.longitude))
    .filter((point): point is Point => point !== null)
  const facilityPoints = facilities.map((facility) => parsePoint(facility.latitude, facility.longitude)).filter((point): point is Point => point !== null)
  const providerPoints = providers.map((provider) => parsePoint(provider.latitude, provider.longitude)).filter((point): point is Point => point !== null)
  const vehiclePoints = displayedVehicles.map((vehicle) => parsePoint(vehicle.latitude, vehicle.longitude)).filter((point): point is Point => point !== null)
  const overviewPoints = [...incidentPoints, ...facilityPoints, ...providerPoints]
  const focusTarget = selectedLocation ? parsePoint(selectedLocation.latitude, selectedLocation.longitude) : null
  const rightPad = panelOpen ? PANEL_WIDTH + 40 : 56

  const refresh = useCallback(async () => {
    setRefreshing(true)
    setError('')
    try {
      const [incidentRows, facilityRows, providerRows] = await Promise.all([getIncidents(), getFacilities(), getProviders()])
      setIncidents(incidentRows)
      setFacilities(facilityRows)
      setProviders(providerRows)
      const selected = incidentRows.find((incident) => incident.id === selectedIncidentId && !TERMINAL_STATUSES.has(incident.status))
        || incidentRows.find((incident) => incident.location && !TERMINAL_STATUSES.has(incident.status))
        || null
      if (selected && selected.id !== selectedIncidentId) setSelectedIncidentId(selected.id)
      if (!selected && selectedIncidentId && incidentRows.some((incident) => incident.id === selectedIncidentId)) {
        setSelectedIncidentId('')
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to load operations map data.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [selectedIncidentId])

  useEffect(() => {
    const timer = window.setTimeout(() => { void refresh() }, 0)
    return () => window.clearTimeout(timer)
  }, [refresh])

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 15_000)
    return () => window.clearInterval(timer)
  }, [])

  useEffect(() => {
    if (!selectedLocation || selectedLocationStale) return
    let active = true
    getNearbyVehicles(selectedLocation.latitude, selectedLocation.longitude, includeSimulation)
      .then((items) => {
        if (active) {
          setVehicleResult({ incidentId: selectedIncidentId, vehicles: items })
        }
      })
      .catch((reason: Error) => { if (active) setError(reason.message) })
    return () => { active = false }
  }, [selectedIncidentId, selectedLocation, selectedLocationStale, includeSimulation])

  function chooseIncident(id: string) {
    setSelectedIncidentId(id)
    setFocusNonce((value) => value + 1)
  }

  function toggleLayer(key: LayerKey) {
    setLayers((current) => ({ ...current, [key]: !current[key] }))
  }

  async function showRoute() {
    if (!selectedIncident?.assigned_vehicle) return
    setRouting(true)
    try {
      const route = await calculateRoute(selectedIncident.id)
      setRouteResult({
        incidentId: selectedIncident.id,
        points: decodePolyline(route.encoded_polyline),
        notice: `${(route.distance_meters / 1000).toFixed(1)} km · ${route.duration_minutes} min${route.is_simulated ? ' · simulated route' : ''} · estimate only, not dispatch confirmation`,
      })
    } catch (reason) {
      setRouteResult({
        incidentId: selectedIncident.id,
        points: [],
        notice: reason instanceof Error ? reason.message : 'Route estimate is unavailable.',
      })
    } finally {
      setRouting(false)
    }
  }

  /* ----------------------------- loading ----------------------------- */

  if (loading) {
    return (
      <div className="operations-map-page" aria-busy="true" aria-label="Loading operations map">
        <div className="ops-skeleton ops-skeleton--head" />
        <div className="ops-skeleton ops-skeleton--stage"><span>Loading operations map…</span></div>
      </div>
    )
  }

  const layerChips: { key: LayerKey; label: string; count: number; icon: typeof Siren }[] = [
    { key: 'incidents', label: 'Incidents', count: locatedIncidents.length, icon: Siren },
    { key: 'facilities', label: 'Facilities', count: facilityPoints.length, icon: Building2 },
    { key: 'providers', label: 'Provider stations', count: providerPoints.length, icon: Ambulance },
    { key: 'vehicles', label: 'Vehicles', count: displayedVehicles.length, icon: Truck },
  ]

  return (
    <div className="operations-map-page">
      {/* ---------- Header ---------- */}
      <header className="ops-head">
        <div>
          <h1>Emergency map</h1>
          <p>Incident snapshots, verified facilities, and only eligible vehicle positions.</p>
        </div>
        <span className="ops-live"><i /> Live view</span>
      </header>

      {error && <div className="ops-error" role="alert">{error}</div>}

      <div className="ops-safety" role="note">
        <Activity size={16} />
        <span>
          Vehicle availability is not dispatch confirmation. Simulated markers are not real ambulances.
          Base maps: OpenStreetMap contributors (Light) and CARTO (Dark).
        </span>
      </div>

      {/* ---------- Map stage ---------- */}
      <div className="ops-stage">
        <MapContainer center={UPSA_CENTER} zoom={12} scrollWheelZoom zoomControl={false} className={`ops-map ops-map--${basemap}`}>
          <TileLayer key={basemap} attribution={BASEMAPS[basemap].attribution} url={BASEMAPS[basemap].url} />
          <ZoomControl position="bottomleft" />
          <FitMap points={overviewPoints} nonce={fitNonce} rightPad={rightPad} />
          <FocusIncident target={focusTarget} vehicles={vehiclePoints} nonce={focusNonce} rightPad={rightPad} />

          {layers.incidents && locatedIncidents.map((incident) => {
            const point = parsePoint(incident.location?.latitude, incident.location?.longitude)
            if (!point || !incident.location) return null
            const stale = isStale(incident.location)
            return (
              <Marker
                key={incident.id}
                position={point}
                icon={markerIcon('incident', { stale, selected: selectedIncidentId === incident.id })}
                zIndexOffset={selectedIncidentId === incident.id ? 1000 : 400}
                eventHandlers={{ click: () => chooseIncident(incident.id) }}
              >
                <Popup>
                  <strong>{words(incident.incident_type)}</strong><br />
                  {incident.priority} · {words(incident.status)}<br />
                  {stale ? 'STALE' : 'Incident-time location snapshot'}<br />
                  Accuracy {incident.location.accuracy_meters ? `±${incident.location.accuracy_meters} m` : 'unknown'} · {ageOf(incident.location.recorded_at)}<br />
                  <Link to={`/incidents/${incident.id}`}>Open incident</Link>
                </Popup>
              </Marker>
            )
          })}

          {layers.facilities && facilities.map((facility) => {
            const point = parsePoint(facility.latitude, facility.longitude)
            if (!point) return null
            return (
              <Marker key={facility.id} position={point} icon={markerIcon('facility')}>
                <Popup><strong>{facility.name}</strong><br />{facility.facility_type} · verified directory record<br />{facility.address}</Popup>
              </Marker>
            )
          })}

          {layers.providers && providers.map((provider) => {
            const point = parsePoint(provider.latitude, provider.longitude)
            if (!point) return null
            return (
              <Marker key={provider.id} position={point} icon={markerIcon('provider')}>
                <Popup><strong>{provider.name}</strong><br />Verified provider station<br />{provider.coverage_description}<br />{provider.address}</Popup>
              </Marker>
            )
          })}

          {layers.vehicles && displayedVehicles.map((vehicle) => {
            const point = parsePoint(vehicle.latitude, vehicle.longitude)
            if (!point) return null
            const locationStale = !vehicle.location_updated_at || now - Date.parse(vehicle.location_updated_at) > STALE_AFTER_MS
            return (
              <Marker
                key={vehicle.id}
                position={point}
                icon={markerIcon('vehicle', { stale: locationStale, simulated: vehicle.is_simulated })}
                zIndexOffset={600}
              >
                <Popup>
                  <strong>{vehicle.vehicle_identifier}</strong><br />
                  {vehicle.provider_name}<br />
                  {vehicle.is_simulated ? 'SIMULATED POSITION' : 'Provider-authorized live feed'}<br />
                  {locationStale ? 'STALE — refresh before relying on this position' : 'Eligible nearby result'} · updated {vehicle.location_updated_at ? new Date(vehicle.location_updated_at).toLocaleString() : 'unknown'}<br />
                  Accuracy {vehicle.location_accuracy_meters == null ? 'unknown' : `±${vehicle.location_accuracy_meters} m`}
                </Popup>
              </Marker>
            )
          })}

          {visibleRoute && visibleRoute.points.length > 1 && (
            <>
              <Polyline positions={visibleRoute.points} pathOptions={{ color: '#3fd8ff', weight: 14, opacity: 0.18, className: 'map-route-glow' }} />
              <Polyline
                positions={visibleRoute.points}
                pathOptions={{
                  color: '#3fd8ff',
                  weight: 5,
                  opacity: 0.95,
                  dashArray: selectedIncident?.is_simulated_dispatch ? '8 8' : undefined,
                  className: selectedIncident?.is_simulated_dispatch ? 'map-route-line map-route-line--sim' : 'map-route-line',
                }}
              />
            </>
          )}
        </MapContainer>

        {/* Toolbar (top-left) */}
        <div className="ops-toolbar">
          <div className="ops-stat"><strong>{activeIncidents.length}</strong><span>active</span></div>
          <div className="ops-stat"><strong>{locatedIncidents.length}</strong><span>located</span></div>
          <div className={`ops-stat${activeIncidents.length - locatedIncidents.length > 0 ? ' is-warn' : ''}`}>
            <strong>{activeIncidents.length - locatedIncidents.length}</strong><span>no location</span>
          </div>
          <span className="ops-toolbar__divider" />
          <div className="ops-segment" role="group" aria-label="Base map style">
            {(Object.keys(BASEMAPS) as Basemap[]).map((key) => (
              <button key={key} type="button" className={basemap === key ? 'is-on' : undefined} onClick={() => setBasemap(key)} aria-pressed={basemap === key}>
                {key === 'dark' ? <Moon size={13} /> : <Sun size={13} />}
                {BASEMAPS[key].label}
              </button>
            ))}
          </div>
          <button type="button" className="ops-icon-btn" onClick={() => { setFitNonce((value) => value + 1) }} aria-label="Reset view to show everything" title="Reset view">
            <Maximize size={15} />
          </button>
          <button type="button" className="ops-icon-btn" onClick={() => void refresh()} disabled={refreshing} aria-label="Refresh data" title="Refresh data">
            <RefreshCw size={15} className={refreshing ? 'is-spinning' : ''} />
          </button>
        </div>

        {/* Layer chips double as the legend (bottom) */}
        <div className="ops-layers" role="group" aria-label="Map layers">
          {layerChips.map(({ key, label, count, icon: Icon }) => (
            <button key={key} type="button" className={`ops-chip ops-chip--${key}${layers[key] ? ' is-on' : ''}`} onClick={() => toggleLayer(key)} aria-pressed={layers[key]}>
              <span className="ops-chip__dot"><Icon size={12} /></span>
              {label}
              <em>{count}</em>
            </button>
          ))}
          <label className="ops-switch">
            <input type="checkbox" role="switch" checked={includeSimulation} onChange={(event) => setIncludeSimulation(event.target.checked)} />
            <span className="ops-switch__track" />
            Simulated vehicles
          </label>
        </div>

        {/* ---------- Side panel ---------- */}
        <aside className={`ops-panel${panelOpen ? '' : ' is-closed'}`} aria-label="Incident panel">
          {selectedIncident && (
            <section className="ops-card ops-selected" key={selectedIncident.id}>
              <header>
                <span className="ops-eyebrow">Selected incident</span>
                <Link to={`/incidents/${selectedIncident.id}`} className="ops-link">Open <ArrowUpRight size={13} /></Link>
              </header>
              <h2>{words(selectedIncident.incident_type)}</h2>
              <div className="ops-badges">
                <StatusBadge value={selectedIncident.priority} />
                <StatusBadge value={selectedIncident.status} />
                {selectedIncident.is_simulated_dispatch && <StatusBadge value="simulated" />}
              </div>

              {selectedIncident.location ? (
                <dl className="ops-facts">
                  <div><dt>Coordinates</dt><dd>{selectedIncident.location.latitude}, {selectedIncident.location.longitude}</dd></div>
                  <div><dt>Accuracy</dt><dd>{selectedIncident.location.accuracy_meters ? `±${selectedIncident.location.accuracy_meters} m` : 'unknown'}</dd></div>
                  <div><dt>Snapshot</dt><dd className={selectedLocationStale ? 'is-warn' : undefined}>{selectedLocationStale ? 'Stale · ' : ''}{ageOf(selectedIncident.location.recorded_at)}</dd></div>
                  <div><dt>Nearby vehicles</dt><dd>{selectedLocationStale ? 'Paused' : displayedVehicles.length}</dd></div>
                </dl>
              ) : (
                <p className="ops-note"><MapPinOff size={14} /> No location snapshot for this incident.</p>
              )}
              {selectedLocationStale && <p className="ops-note ops-note--warn">Location is stale, so nearby vehicle results are hidden until a fresh position arrives.</p>}

              {selectedIncident.assigned_vehicle && (
                <button type="button" className={`ops-route-btn${routing ? ' is-loading' : ''}`} onClick={() => void showRoute()} disabled={routing}>
                  <RouteIcon size={16} />
                  <span>{routing ? 'Calculating…' : 'Show assigned route and ETA'}</span>
                  <i aria-hidden="true" />
                </button>
              )}
              {visibleRoute?.notice && <p className="ops-route-notice" role="status">{visibleRoute.notice}</p>}
            </section>
          )}

          <section className="ops-card ops-list-card">
            <header>
              <span className="ops-eyebrow">Active response</span>
              <span className="ops-count">{activeIncidents.length}</span>
            </header>
            {activeIncidents.length === 0 ? (
              <EmptyState icon={Crosshair} title="No active incidents" detail="No active incidents returned for your account." />
            ) : (
              <ul className="ops-list">
                {activeIncidents.map((incident, index) => {
                  const stale = incident.location ? isStale(incident.location) : false
                  const state = !incident.location ? 'none' : stale ? 'stale' : 'live'
                  return (
                    <li key={incident.id} style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}>
                      <button type="button" className={`ops-row ops-row--${state}${incident.id === selectedIncidentId ? ' is-selected' : ''}`} onClick={() => chooseIncident(incident.id)}>
                        <span className="ops-row__main">
                          <strong>{words(incident.incident_type)}</strong>
                          <small>{incident.priority} · {words(incident.status)}</small>
                          <small className="ops-row__loc">
                            {incident.location
                              ? `${stale ? 'STALE · ' : ''}${incident.location.latitude}, ${incident.location.longitude} · ±${incident.location.accuracy_meters ?? 'unknown'} m · ${ageOf(incident.location.recorded_at)}`
                              : 'No location snapshot'}
                          </small>
                        </span>
                      </button>
                      <Link className="ops-row__open" to={`/incidents/${incident.id}`} aria-label="Open incident"><ArrowUpRight size={15} /></Link>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        </aside>

        {/* Panel toggle */}
        <button
          type="button"
          className={`ops-panel-toggle${panelOpen ? ' is-open' : ''}`}
          onClick={() => setPanelOpen((open) => !open)}
          aria-expanded={panelOpen}
          aria-label={panelOpen ? 'Hide incident panel' : 'Show incident panel'}
        >
          {panelOpen ? <PanelRightClose size={17} /> : <PanelRightOpen size={17} />}
        </button>
      </div>
    </div>
  )
}