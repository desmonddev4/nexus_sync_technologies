import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  ArrowLeft,
  ArrowUpRight,
  BatteryMedium,
  Check,
  Clock3,
  Copy,
  Cpu,
  HeartPulse,
  MapPin,
  Phone,
  ShieldAlert,
  ShieldCheck,
  Siren,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getIncidents, getPatient, getPatientDevices, getPatientLocations, getPatientMeasurements } from '../../api/operations'
import type { DeviceHealth, Incident, Measurement, Patient, PatientLocation } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { MetricTile } from '../../components/MetricTile/MetricTile'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './PatientDetailPage.css'

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const terminalStatuses = ['resolved', 'closed', 'cancelled']
const fmt = (value: string) => new Date(value).toLocaleString()
const words = (value: string) => value.replaceAll('_', ' ')

function initials(name: string) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'P'
}

function Panel({
  icon: Icon,
  title,
  aside,
  delay = 0,
  className = '',
  children,
}: {
  icon: LucideIcon
  title: string
  aside?: ReactNode
  delay?: number
  className?: string
  children: ReactNode
}) {
  return (
    <section className={`detail-panel ${className}`} style={{ animationDelay: `${delay}ms` }}>
      <div className="detail-panel-heading">
        <h2>
          <span className="detail-panel-icon"><Icon size={16} aria-hidden="true" /></span>
          {title}
        </h2>
        {aside}
      </div>
      {children}
    </section>
  )
}

function BatteryBar({ percent }: { percent: number | null }) {
  if (percent === null) return <span><BatteryMedium size={14} /> n/a</span>
  const level = percent < 20 ? 'low' : percent < 50 ? 'mid' : 'ok'
  return (
    <span className="battery">
      <i className={`battery-bar battery-bar--${level}`}><b style={{ width: `${Math.max(4, percent)}%` }} /></i>
      {percent}%
    </span>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const [patient, setPatient] = useState<Patient | null>(null)
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [locations, setLocations] = useState<PatientLocation[]>([])
  const [devices, setDevices] = useState<DeviceHealth[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    let active = true
    Promise.all([
      getPatient(patientId),
      getIncidents(),
      getPatientMeasurements(patientId, 10),
      getPatientLocations(patientId, 10),
      getPatientDevices(patientId),
    ])
      .then(([currentPatient, allIncidents, recentMeasurements, recentLocations, patientDevices]) => {
        if (!active) return
        setPatient(currentPatient)
        setIncidents(allIncidents)
        setMeasurements(recentMeasurements)
        setLocations(recentLocations)
        setDevices(patientDevices)
      })
      .catch((reason: Error) => {
        if (!active) return
        setError(reason.message)
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [patientId])

  const patientIncidents = useMemo(
    () => incidents
      .filter((incident) => incident.patient === patientId)
      .sort((first, second) => Date.parse(second.created_at) - Date.parse(first.created_at)),
    [incidents, patientId],
  )

  const activeIncidents = patientIncidents.filter((incident) => !terminalStatuses.includes(incident.status))

  if (loading) {
    return (
      <div className="patient-detail-page" aria-busy="true" aria-label="Loading patient record">
        <div className="pd-skeleton pd-skeleton--hero" />
        <div className="pd-skeleton-row"><i /><i /><i /><i /></div>
        <div className="pd-skeleton pd-skeleton--panel" />
      </div>
    )
  }
  if (!patient) return <div className="page-error" role="alert">{error || 'Patient not found.'}</div>

  const contacts = patient.emergency_contacts || []
  const consents = patient.consent_records || []

  async function copyId() {
    try {
      await navigator.clipboard.writeText(patient!.id)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable — ignore */
    }
  }

  return (
    <div className="patient-detail-page">
      <Link to="/patients" className="back-link"><ArrowLeft size={15} /> Patient directory</Link>

      {/* ---------- Hero ---------- */}
      <header className="patient-hero">
        <span className="patient-avatar" aria-hidden="true">{initials(patient.full_name)}</span>
        <div className="patient-hero__copy">
          <div className="patient-hero__title">
            <h1>{patient.full_name}</h1>
            <StatusBadge value={patient.status} />
          </div>
          <p>Record created {fmt(patient.created_at)}</p>
          <button type="button" className={`copy-chip${copied ? ' is-copied' : ''}`} onClick={copyId} aria-label="Copy patient identifier">
            <span>ID {patient.id.slice(0, 8)}</span>
            {copied ? <Check size={13} /> : <Copy size={13} />}
            <em>{copied ? 'Copied' : 'Copy'}</em>
          </button>
        </div>
      </header>

      {error && <div className="page-error" role="alert">Unable to load full patient context: {error}</div>}

      {/* ---------- Summary tiles ---------- */}
      <section className="pd-metrics" aria-label="Patient summary">
        <MetricTile label="Active incidents" value={activeIncidents.length} detail="Not yet closed" icon={Siren} tone="coral" />
        <MetricTile label="Linked incidents" value={patientIncidents.length} detail={`${patientIncidents.length - activeIncidents.length} closed out`} icon={Clock3} tone="blue" />
        <MetricTile label="Assigned devices" value={devices.length} detail={devices.some((d) => d.is_stale) ? 'Some devices are stale' : 'Reporting normally'} icon={Cpu} tone="green" />
        <MetricTile label="Emergency contacts" value={contacts.length} detail={patient.phone_number ? 'Patient phone recorded' : 'No patient phone recorded'} icon={Users} tone="amber" />
      </section>

      <div className="patient-detail-grid">
        {/* ---------- Main column ---------- */}
        <div className="pd-main">
          <Panel icon={HeartPulse} title="Readings and location history" delay={60}>
            <div className="detail-subgrid">
              <article>
                <h3>Recent readings</h3>
                {measurements.length === 0 ? (
                  <p className="detail-empty">No measurement data recorded.</p>
                ) : (
                  <div className="stack-list">
                    {measurements.map((measurement) => (
                      <div className="stack-item" key={measurement.id}>
                        <div>
                          <strong>{words(measurement.measurement_type)}</strong>
                          <small>{measurement.source} · {measurement.quality}</small>
                        </div>
                        <div className="stack-item__end">
                          <span>{measurement.value} {measurement.unit}</span>
                          <small>{fmt(measurement.measured_at)}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </article>

              <article>
                <h3><MapPin size={14} /> Recent locations</h3>
                {locations.length === 0 ? (
                  <p className="detail-empty">No location history recorded.</p>
                ) : (
                  <div className="stack-list">
                    {locations.map((location) => (
                      <div className="stack-item" key={location.id}>
                        <div>
                          <strong>{location.latitude}, {location.longitude}</strong>
                          <small>{location.source} · {location.quality}</small>
                        </div>
                        <div className="stack-item__end">
                          <span>{location.accuracy_meters ? `±${location.accuracy_meters} m` : 'accuracy n/a'}</span>
                          <small>{fmt(location.recorded_at)}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            </div>
          </Panel>

          <Panel
            icon={Siren}
            title="Incidents linked to this patient"
            delay={120}
            aside={<span className="patient-incidents-count">{patientIncidents.length} total</span>}
          >
            <div className="metric-strip" aria-label="Patient incident summary">
              <div><Clock3 size={15} /><span>{activeIncidents.length} active</span></div>
              <div><Check size={15} /><span>{patientIncidents.length - activeIncidents.length} terminal</span></div>
              <div><Phone size={15} /><span>{patient.phone_number ? 'Phone recorded' : 'No phone recorded'}</span></div>
            </div>

            {patientIncidents.length === 0 ? (
              <EmptyState icon={Clock3} title="No incidents yet" detail="New SOS and rule-triggered incidents for this patient will appear here." />
            ) : (
              <div className="table-wrap">
                <table className="data-table">
                  <thead>
                    <tr><th>Incident</th><th>Priority</th><th>Status</th><th>Created</th><th /></tr>
                  </thead>
                  <tbody>
                    {patientIncidents.map((incident) => (
                      <tr key={incident.id}>
                        <td>
                          <Link className="incident-link" to={`/incidents/${incident.id}`}>{words(incident.incident_type)}</Link>
                          <small>{incident.trigger_source} · #{incident.id.slice(0, 8)}</small>
                        </td>
                        <td><StatusBadge value={incident.priority} /></td>
                        <td><StatusBadge value={incident.status} /></td>
                        <td>{fmt(incident.created_at)}</td>
                        <td>
                          <Link to={`/incidents/${incident.id}`} className="row-open" aria-label="Open incident">
                            <ArrowUpRight size={15} />
                          </Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
        </div>

        {/* ---------- Side column ---------- */}
        <aside className="pd-side">
          <Panel icon={ShieldAlert} title="Patient profile" delay={90}>
            <div className="profile-grid">
              <article><p>Identifier</p><strong>{patient.id}</strong></article>
              <article><p>Phone</p><strong>{patient.phone_number || 'No phone on record'}</strong></article>
              <article><p>Date of birth</p><strong>{patient.date_of_birth || 'Not recorded'}</strong></article>
              <article><p>Last updated</p><strong>{fmt(patient.updated_at)}</strong></article>
            </div>
            <div className="notes-box">
              <div className="notes-heading"><ShieldAlert size={15} /><span>Relevant medical notes</span></div>
              <p>{patient.relevant_medical_notes || 'No medical notes recorded.'}</p>
            </div>
          </Panel>

          <Panel
            icon={Cpu}
            title="Assigned devices"
            delay={150}
            aside={<span className="patient-incidents-count">{devices.length} device(s)</span>}
          >
            {devices.length === 0 ? (
              <p className="detail-empty">No devices are currently assigned to this patient.</p>
            ) : (
              <div className="stack-list">
                {devices.map((device) => (
                  <div className="stack-item" key={device.id}>
                    <div>
                      <strong>{device.device_identifier}</strong>
                      <small>{words(device.device_type)} · {device.status}</small>
                    </div>
                    <div className="stack-item__end">
                      <BatteryBar percent={device.battery_percent} />
                      <small>
                        {device.last_seen_at ? `Seen ${fmt(device.last_seen_at)}` : 'Never seen'}
                        {device.is_stale ? ' · stale' : ''}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel icon={Users} title="Emergency contacts" delay={210}>
            {contacts.length === 0 ? (
              <p className="detail-empty">No emergency contacts recorded.</p>
            ) : (
              <div className="stack-list">
                {contacts.map((contact) => (
                  <div className="stack-item" key={contact.id}>
                    <div>
                      <strong>{contact.name}</strong>
                      <small>{contact.relationship || 'Relationship not recorded'} · Priority {contact.priority_order}</small>
                    </div>
                    <div className="stack-item__end">
                      <a className="phone-link" href={`tel:${contact.phone_number}`}><Phone size={13} /> {contact.phone_number}</a>
                      <StatusBadge value={contact.verification_status} />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel icon={ShieldCheck} title="Consent history" delay={270}>
            {consents.length === 0 ? (
              <p className="detail-empty">No consent records available.</p>
            ) : (
              <div className="stack-list">
                {consents.map((consent) => (
                  <div className="stack-item" key={consent.id}>
                    <div>
                      <strong>{words(consent.scope)}</strong>
                      <small>Policy {consent.policy_version}</small>
                    </div>
                    <div className="stack-item__end">
                      <span>{consent.status}</span>
                      <small>{fmt(consent.recorded_at)}</small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </aside>
      </div>
    </div>
  )
}