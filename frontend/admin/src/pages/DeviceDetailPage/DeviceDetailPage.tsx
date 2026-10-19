import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, BatteryCharging, CloudUpload, HeartPulse, MapPin, ShieldCheck, Siren, Watch, Wifi } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { getDeviceRegistry, getPatientLocations, getPatientMeasurements, getPatients } from '../../api/operations'
import type { DeviceRegistryRecord, Measurement, Patient, PatientLocation } from '../../types/api'
import { BandIllustration } from '../WearableDemoPage/WearableDemoPage'
import './DeviceDetailPage.css'

const fmt = (value: string | null | undefined) => value ? new Date(value).toLocaleString() : 'Not available'
const words = (value: string) => value.replaceAll('_', ' ')

function signalText(level: number | null) {
  if (level === null) return 'No signal'
  if (level >= 80) return 'Strong'
  if (level >= 55) return 'Stable'
  return 'Weak'
}

export function DeviceDetailPage() {
  const { deviceId = '' } = useParams()
  const [device, setDevice] = useState<DeviceRegistryRecord | null>(null)
  const [patient, setPatient] = useState<Patient | null>(null)
  const [measurements, setMeasurements] = useState<Measurement[]>([])
  const [locations, setLocations] = useState<PatientLocation[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true

    async function load() {
      try {
        const [registry, patientRows] = await Promise.all([getDeviceRegistry(), getPatients()])
        const selected = registry.find((entry) => entry.id === deviceId) ?? null

        if (!active) return
        setDevice(selected)

        if (!selected) {
          return
        }

        const patientId = selected.patient
        const patientRecord = patientId ? patientRows.find((entry) => entry.id === patientId) ?? null : null
        setPatient(patientRecord)

        if (!patientId) {
          setMeasurements([])
          setLocations([])
          return
        }

        const [latestMeasurements, latestLocations] = await Promise.all([
          getPatientMeasurements(patientId, 12),
          getPatientLocations(patientId, 12),
        ])

        if (!active) return
        setMeasurements(latestMeasurements.filter((entry) => entry.device === selected.id || !entry.device))
        setLocations(latestLocations.filter((entry) => entry.device === selected.id || !entry.device))
      } catch (reason) {
        if (!active) return
        setError(reason instanceof Error ? reason.message : 'Unable to load device overview.')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [deviceId])

  const heartRate = useMemo(() => {
    const sample = measurements
      .filter((item) => item.measurement_type === 'heart_rate_bpm' || item.measurement_type === 'heart_rate')
      .sort((a, b) => Date.parse(b.measured_at) - Date.parse(a.measured_at))[0]
    return sample ? Number(sample.value) : null
  }, [measurements])

  const latestLocation = useMemo(() => {
    return [...locations].sort((a, b) => Date.parse(b.recorded_at) - Date.parse(a.recorded_at))[0] ?? null
  }, [locations])

  if (loading) {
    return <div className="device-detail-page device-detail-page--loading">Loading device overview…</div>
  }

  if (!device) {
    return <div className="page-error" role="alert">{error || 'Device not found.'}</div>
  }

  const batteryPercent = typeof device.battery_percent === 'number' ? device.battery_percent : 0

  return (
    <div className="device-detail-page">
      <Link className="back-link" to="/devices"><ArrowLeft size={15} /> Devices</Link>

      <header className="device-hero">
        <div className="device-hero__band">
          <BandIllustration />
        </div>

        <div className="device-hero__copy">
          <div className="device-hero__meta">
            <span className="device-pill">{words(device.device_type)}</span>
            <span className="device-pill device-pill--muted">{device.status}</span>
          </div>
          <h1>{device.device_identifier}</h1>
          <p>Device credential: {device.credential_revoked ? 'revoked' : 'active'} · last seen {fmt(device.last_seen_at)}</p>
        </div>
      </header>

      {error && <div className="page-error" role="alert">{error}</div>}

      <section className="device-metrics" aria-label="Device metrics">
        <div className="metric-card">
          <HeartPulse size={18} />
          <div><small>Heart rate</small><strong>{heartRate ?? '--'} bpm</strong></div>
        </div>
        <div className="metric-card">
          <BatteryCharging size={18} />
          <div><small>Battery</small><strong>{batteryPercent}%</strong></div>
        </div>
        <div className="metric-card">
          <Wifi size={18} />
          <div><small>Signal</small><strong>{signalText(device.battery_percent !== null && device.battery_percent !== undefined ? Math.max(20, Math.min(100, device.battery_percent + 20)) : 92)}</strong></div>
        </div>
        <div className="metric-card">
          <CloudUpload size={18} />
          <div><small>Data source</small><strong>{device.device_type === 'simulator' ? 'simulated' : 'device telemetry'}</strong></div>
        </div>
      </section>

      <div className="device-layout">
        <section className="device-panel">
          <div className="device-panel__header">
            <h2><Watch size={16} /> Device status</h2>
          </div>
          <div className="device-summary-grid">
            <div><span>FHIR / registry ID</span><strong>{device.id.slice(0, 8)}</strong></div>
            <div><span>Firmware</span><strong>{device.firmware_version}</strong></div>
            <div><span>Assigned patient</span><strong>{patient ? patient.full_name : 'Unassigned'}</strong></div>
            <div><span>Last seen</span><strong>{fmt(device.last_seen_at)}</strong></div>
            <div><span>Authentication</span><strong>{device.credential_revoked ? 'Revoked' : 'Active'}</strong></div>
            <div><span>OS / health</span><strong>{device.status}</strong></div>
          </div>
        </section>

        <section className="device-panel">
          <div className="device-panel__header">
            <h2><MapPin size={16} /> Location</h2>
          </div>
          {latestLocation ? (
            <div className="location-card">
              <p>{latestLocation.latitude}, {latestLocation.longitude}</p>
              <small>{latestLocation.source} · accuracy {latestLocation.accuracy_meters ?? 'n/a'}m · {fmt(latestLocation.recorded_at)}</small>
            </div>
          ) : (
            <p className="empty-note">No location received yet.</p>
          )}
        </section>
      </div>

      <div className="device-layout device-layout--bottom">
        <section className="device-panel">
          <div className="device-panel__header">
            <h2><ShieldCheck size={16} /> Patient context</h2>
          </div>
          {patient ? (
            <div className="patient-context-card">
              <strong>{patient.full_name}</strong>
              <small>{patient.phone_number || 'No phone recorded'}</small>
              <small>{patient.date_of_birth || 'DOB not recorded'}</small>
            </div>
          ) : (
            <p className="empty-note">This device is not linked to a patient.</p>
          )}
        </section>

        <section className="device-panel">
          <div className="device-panel__header">
            <h2><Siren size={16} /> Recent telemetry</h2>
          </div>
          {measurements.length === 0 ? (
            <p className="empty-note">No telemetry has been logged yet.</p>
          ) : (
            <div className="telemetry-list">
              {measurements.slice(0, 6).map((item) => (
                <div className="telemetry-row" key={item.id}>
                  <div>
                    <strong>{words(item.measurement_type)}</strong>
                    <small>{fmt(item.measured_at)}</small>
                  </div>
                  <span>{item.value} {item.unit}</span>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
