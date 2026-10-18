import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, ArrowUpRight, BatteryMedium, Clock3, Phone, ShieldAlert, UserRound } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getIncidents, getPatient, getPatientDevices, getPatientLocations, getPatientMeasurements } from '../../api/operations'
import type { DeviceHealth, Incident, Measurement, Patient, PatientLocation } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './PatientDetailPage.css'

export function PatientDetailPage() {
  const { patientId = '' } = useParams()
  const [patient, setPatient] = useState<Patient | null>(null)
  const [incidents, setIncidents] = useState<Incident[]>([])
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [locations, setLocations] = useState<PatientLocation[]>([])
  const [devices, setDevices] = useState<DeviceHealth[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

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

  const activeIncidents = patientIncidents.filter((incident) => !['resolved', 'closed', 'cancelled'].includes(incident.status))

  if (loading) return <div className="patient-detail-loading">Loading patient record…</div>
  if (!patient) return <div className="page-error" role="alert">{error || 'Patient not found.'}</div>

  const contacts = patient.emergency_contacts || []
  const consents = patient.consent_records || []

  return (
    <div className="patient-detail-page">
      <Link to="/patients" className="back-link"><ArrowLeft size={15} /> Patient directory</Link>
      <header className="patient-detail-heading">
        <div>
          <p className="page-eyebrow">PATIENT / {patient.id.slice(0, 8).toUpperCase()}</p>
          <h1>{patient.full_name}</h1>
          <p className="page-subtitle">Record created {new Date(patient.created_at).toLocaleString()}</p>
        </div>
        <StatusBadge value={patient.status} />
      </header>

      {error && <div className="page-error" role="alert">Unable to load full patient context: {error}</div>}

      <div className="patient-detail-grid">
        <section className="detail-panel">
          <div className="detail-panel-heading">
            <div>
              <p className="page-eyebrow">PROFILE</p>
              <h2>Patient profile</h2>
            </div>
          </div>
          <div className="profile-grid">
            <article>
              <p>Identifier</p>
              <strong>{patient.id}</strong>
            </article>
            <article>
              <p>Phone</p>
              <strong>{patient.phone_number || 'No phone on record'}</strong>
            </article>
            <article>
              <p>Date of birth</p>
              <strong>{patient.date_of_birth || 'Not recorded'}</strong>
            </article>
            <article>
              <p>Last updated</p>
              <strong>{new Date(patient.updated_at).toLocaleString()}</strong>
            </article>
          </div>
          <div className="notes-box">
            <div className="notes-heading"><ShieldAlert size={16} /><span>Relevant medical notes</span></div>
            <p>{patient.relevant_medical_notes || 'No medical notes recorded.'}</p>
          </div>
        </section>

        <section className="detail-panel">
          <div className="detail-panel-heading">
            <div>
              <p className="page-eyebrow">RECENT MONITORING</p>
              <h2>Readings and location history</h2>
            </div>
          </div>

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
                        <strong>{measurement.measurement_type.replaceAll('_', ' ')}</strong>
                        <small>{measurement.source} · {measurement.quality}</small>
                      </div>
                      <div>
                        <span>{measurement.value} {measurement.unit}</span>
                        <small>{new Date(measurement.measured_at).toLocaleString()}</small>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article>
              <h3>Recent locations</h3>
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
                      <div>
                        <span>{location.accuracy_meters ? `±${location.accuracy_meters} m` : 'accuracy n/a'}</span>
                        <small>{new Date(location.recorded_at).toLocaleString()}</small>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </section>

        <section className="detail-panel">
          <div className="detail-panel-heading">
            <div>
              <p className="page-eyebrow">DEVICE HEALTH</p>
              <h2>Assigned devices</h2>
            </div>
            <span className="patient-incidents-count">{devices.length} device(s)</span>
          </div>
          {devices.length === 0 ? (
            <p className="detail-empty">No devices are currently assigned to this patient.</p>
          ) : (
            <div className="stack-list">
              {devices.map((device) => (
                <div className="stack-item" key={device.id}>
                  <div>
                    <strong>{device.device_identifier}</strong>
                    <small>{device.device_type.replaceAll('_', ' ')} · {device.status}</small>
                  </div>
                  <div>
                    <span><BatteryMedium size={14} /> {device.battery_percent === null ? 'n/a' : `${device.battery_percent}%`}</span>
                    <small>{device.last_seen_at ? `Seen ${new Date(device.last_seen_at).toLocaleString()}` : 'Never seen'}{device.is_stale ? ' · stale' : ''}</small>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="detail-panel">
          <div className="detail-panel-heading">
            <div>
              <p className="page-eyebrow">CONSENT AND CONTACTS</p>
              <h2>Emergency contacts and consent history</h2>
            </div>
          </div>

          <div className="detail-subgrid">
            <article>
              <h3>Emergency contacts</h3>
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
                      <div>
                        <span>{contact.phone_number}</span>
                        <small>{contact.verification_status}</small>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>

            <article>
              <h3>Consent history</h3>
              {consents.length === 0 ? (
                <p className="detail-empty">No consent records available.</p>
              ) : (
                <div className="stack-list">
                  {consents.map((consent) => (
                    <div className="stack-item" key={consent.id}>
                      <div>
                        <strong>{consent.scope.replaceAll('_', ' ')}</strong>
                        <small>Policy {consent.policy_version}</small>
                      </div>
                      <div>
                        <span>{consent.status}</span>
                        <small>{new Date(consent.recorded_at).toLocaleString()}</small>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </article>
          </div>
        </section>

        <section className="detail-panel">
          <div className="detail-panel-heading">
            <div>
              <p className="page-eyebrow">INCIDENT HISTORY</p>
              <h2>Incidents linked to this patient</h2>
            </div>
            <span className="patient-incidents-count">{patientIncidents.length} total</span>
          </div>

          <div className="metric-strip" aria-label="Patient incident summary">
            <div><Clock3 size={15} /><span>{activeIncidents.length} active</span></div>
            <div><UserRound size={15} /><span>{patientIncidents.length - activeIncidents.length} terminal</span></div>
            <div><Phone size={15} /><span>{patient.phone_number ? 'Phone recorded' : 'No phone recorded'}</span></div>
          </div>

          {patientIncidents.length === 0 ? (
            <EmptyState icon={Clock3} title="No incidents yet" detail="New SOS and rule-triggered incidents for this patient will appear here." />
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Incident</th>
                    <th>Priority</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {patientIncidents.map((incident) => (
                    <tr key={incident.id}>
                      <td>
                        <Link className="incident-link" to={`/incidents/${incident.id}`}>
                          {incident.incident_type.replaceAll('_', ' ')}
                        </Link>
                        <small>{incident.trigger_source} · #{incident.id.slice(0, 8)}</small>
                      </td>
                      <td><StatusBadge value={incident.priority} /></td>
                      <td><StatusBadge value={incident.status} /></td>
                      <td>{new Date(incident.created_at).toLocaleString()}</td>
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
        </section>
      </div>
    </div>
  )
}
