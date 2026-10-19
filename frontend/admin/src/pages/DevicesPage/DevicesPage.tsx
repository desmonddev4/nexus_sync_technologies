import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Check, CheckCircle2, Copy, Cpu, KeyRound, Plus, RefreshCw, Search, ShieldOff, Smartphone, Watch, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { createRegistryDevice, getDeviceRegistry, getPatients, issueDeviceCredential, revokeDeviceCredential, updateRegistryDevice } from '../../api/operations'
import type { DeviceRegistryRecord, IssuedDeviceCredential, Patient } from '../../types/api'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './DevicesPage.css'

const initialDraft = { device_identifier: '', device_type: 'simulator', patient: '', status: 'registered' }

const STATUSES = ['registered', 'active', 'inactive', 'revoked'] as const
const TYPE_ICONS: Record<string, LucideIcon> = { wearable: Watch, phone_gateway: Smartphone, simulator: Cpu }
const words = (value: string) => value.replaceAll('_', ' ')

export function DevicesPage() {
  const [devices, setDevices] = useState<DeviceRegistryRecord[]>([])
  const [patients, setPatients] = useState<Patient[]>([])
  const [draft, setDraft] = useState(initialDraft)
  const [issued, setIssued] = useState<IssuedDeviceCredential | null>(null)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [confirmRevokeId, setConfirmRevokeId] = useState('')
  const [secretCopied, setSecretCopied] = useState(false)

  async function load() {
    const [deviceRows, patientRows] = await Promise.all([getDeviceRegistry(), getPatients()])
    setDevices(deviceRows)
    setPatients(patientRows)
  }

  useEffect(() => {
    let active = true
    Promise.all([getDeviceRegistry(), getPatients()])
      .then(([deviceRows, patientRows]) => { if (active) { setDevices(deviceRows); setPatients(patientRows) } })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  async function createDevice(event: FormEvent) {
    event.preventDefault()
    setBusyId('new')
    setError('')
    setNotice('')
    try {
      await createRegistryDevice({ ...draft, patient: draft.patient || null })
      setDraft(initialDraft)
      await load()
      setNotice('Device registered. Assign it to a patient and activate it before issuing credentials.')
    } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to register device.') }
    finally { setBusyId('') }
  }

  async function assignPatient(device: DeviceRegistryRecord, patientId: string) {
    setBusyId(device.id)
    setError('')
    try { await updateRegistryDevice(device.id, { patient: patientId || null }); await load() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to update device assignment.') }
    finally { setBusyId('') }
  }

  async function changeStatus(device: DeviceRegistryRecord, status: string) {
    if (status === device.status) return
    setBusyId(device.id)
    setError('')
    try { await updateRegistryDevice(device.id, { status }); await load() }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to update device status.') }
    finally { setBusyId('') }
  }

  async function issue(device: DeviceRegistryRecord) {
    setBusyId(device.id)
    setError('')
    setNotice('')
    setSecretCopied(false)
    try { setIssued(await issueDeviceCredential(device.id)) }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to issue device credential.') }
    finally { setBusyId('') }
  }

  async function revoke(device: DeviceRegistryRecord) {
    // Revoking is destructive, so the first click arms the button and the second confirms.
    if (confirmRevokeId !== device.id) {
      setConfirmRevokeId(device.id)
      window.setTimeout(() => setConfirmRevokeId((current) => (current === device.id ? '' : current)), 4000)
      return
    }
    setConfirmRevokeId('')
    setBusyId(device.id)
    setError('')
    try { await revokeDeviceCredential(device.id); setIssued(null); await load(); setNotice('Credential revoked. Device authentication will no longer accept it.') }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to revoke credential.') }
    finally { setBusyId('') }
  }

  async function copySecret() {
    if (!issued) return
    try {
      await navigator.clipboard.writeText(issued.secret)
      setSecretCopied(true)
      setNotice('Credential copied. Store it securely; it will not be shown again.')
    } catch { setError('Clipboard access was denied. Copy the credential manually and store it securely.') }
  }

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const device of devices) counts.set(device.status, (counts.get(device.status) ?? 0) + 1)
    return counts
  }, [devices])

  const needle = query.trim().toLowerCase()
  const visible = devices.filter((device) =>
    (statusFilter === 'all' || device.status === statusFilter) &&
    (!needle || `${device.device_identifier} ${device.device_type}`.toLowerCase().includes(needle)),
  )

  const patientName = (id: string | null) => patients.find((patient) => patient.id === id)?.full_name

  return (
    <div className="ui-page devices-page">
      <header className="ui-head">
        <div>
          <h1>Devices</h1>
          <p>Register hardware, link it to a patient, then activate and issue its credential.</p>
        </div>
        <div className="ui-head__aside">
          <span className="ui-pill"><strong>{devices.length}</strong> registered</span>
          <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => { setLoading(true); load().catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false)) }} aria-label="Refresh device registry">
            <RefreshCw size={14} className={loading ? 'dv-spin' : undefined} /> Refresh
          </button>
        </div>
      </header>

      {error && <div className="ui-error" role="alert">{error}</div>}
      {notice && <div className="ui-notice ui-notice--info" role="status"><CheckCircle2 size={16} /><span>{notice}</span></div>}

      {issued && (
        <section className="dv-credential" aria-label="New device credential">
          <div className="dv-credential__icon"><KeyRound size={20} /></div>
          <div className="dv-credential__body">
            <strong>Credential shown once</strong>
            <p>{issued.warning} Never paste it into chat or commit it.</p>
            <code>{issued.secret}</code>
          </div>
          <div className="dv-credential__actions">
            <button type="button" className={`ui-btn ui-btn--sm${secretCopied ? ' is-copied' : ''}`} onClick={copySecret}>
              {secretCopied ? <Check size={15} /> : <Copy size={15} />} {secretCopied ? 'Copied' : 'Copy secret'}
            </button>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setIssued(null)}>Dismiss</button>
          </div>
        </section>
      )}

      <div className="device-provision-grid">
        {/* ---------- Register ---------- */}
        <section className="ui-panel dv-register">
          <div className="ui-panel__head">
            <h2><span className="ui-panel__icon"><Plus size={16} /></span> Register device</h2>
          </div>
          <p className="ui-muted dv-hint">Device identifiers must be unique.</p>
          <form className="dv-form" onSubmit={createDevice}>
            <label className="ui-field">Device identifier<input required maxLength={100} value={draft.device_identifier} onChange={(event) => setDraft({ ...draft, device_identifier: event.target.value })} placeholder="e.g. NS-WEARABLE-001" /></label>
            <label className="ui-field">Type<select value={draft.device_type} onChange={(event) => setDraft({ ...draft, device_type: event.target.value })}><option value="simulator">Simulator</option><option value="wearable">Wearable</option><option value="phone_gateway">Phone gateway</option><option value="other">Other</option></select></label>
            <label className="ui-field">Patient assignment<select value={draft.patient} onChange={(event) => setDraft({ ...draft, patient: event.target.value })}><option value="">Not assigned</option>{patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.full_name}</option>)}</select></label>
            <label className="ui-field">Initial status<select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value })}><option value="registered">Registered</option><option value="active">Active</option><option value="inactive">Inactive</option></select></label>
            <button className={`ui-btn${busyId === 'new' ? ' is-busy' : ''}`} type="submit" disabled={busyId === 'new'}>{busyId === 'new' ? 'Registering…' : 'Register device'}</button>
          </form>
        </section>

        {/* ---------- Registry ---------- */}
        <section className="ui-panel device-list-panel">
          <div className="ui-panel__head">
            <h2><span className="ui-panel__icon"><Watch size={16} /></span> Registered devices</h2>
          </div>
          <p className="ui-muted dv-hint">Secrets are never listed or stored in plaintext.</p>

          <div className="dv-controls">
            <div className="ui-search">
              <Search size={16} />
              <input aria-label="Search devices" placeholder="Search identifier or type…" value={query} onChange={(event) => setQuery(event.target.value)} />
              {query && <button type="button" className="ui-search__clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}
            </div>
            <div className="dv-chips" role="group" aria-label="Filter by status">
              <button type="button" className={`ui-chip${statusFilter === 'all' ? ' is-on' : ''}`} onClick={() => setStatusFilter('all')} aria-pressed={statusFilter === 'all'}>All {devices.length}</button>
              {STATUSES.filter((status) => statusCounts.has(status)).map((status) => (
                <button key={status} type="button" className={`ui-chip${statusFilter === status ? ' is-on' : ''}`} onClick={() => setStatusFilter(status)} aria-pressed={statusFilter === status}>{status} {statusCounts.get(status)}</button>
              ))}
            </div>
          </div>

          {loading ? (
            <div className="ui-skeleton-stack" aria-busy="true"><div className="ui-skeleton" style={{ height: 150 }} /><div className="ui-skeleton" style={{ height: 150 }} /></div>
          ) : visible.length === 0 ? (
            <p className="dv-empty">{devices.length === 0 ? 'No registered devices yet.' : 'No devices match the current search or filter.'}</p>
          ) : (
            <div className="device-list">
              {visible.map((device, index) => {
                const Icon = TYPE_ICONS[device.device_type] ?? Cpu
                const linked = Boolean(device.patient)
                const active = device.status === 'active'
                const canIssue = active && linked && ['wearable', 'simulator'].includes(device.device_type)
                const busy = busyId === device.id
                return (
                  <article className={`device-row${busy ? ' is-busy' : ''}`} key={device.id} style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}>
                    <div className="device-row__head">
                      <span className="dv-type-icon"><Icon size={19} /></span>
                      <div>
                        <strong>{device.device_identifier}</strong>
                        <small>{words(device.device_type)} · {device.last_seen_at ? `last seen ${new Date(device.last_seen_at).toLocaleString()}` : 'never connected'}</small>
                      </div>
                      <StatusBadge value={device.status} />
                    </div>

                    {/* Provisioning progress */}
                    <ol className="dv-steps" aria-label="Provisioning progress">
                      <li className="is-done"><Check size={12} /> Registered</li>
                      <li className={linked ? 'is-done' : undefined}>{linked ? <Check size={12} /> : <span />} {linked ? `Linked to ${patientName(device.patient) ?? 'patient'}` : 'Not linked to a patient'}</li>
                      <li className={active ? 'is-done' : undefined}>{active ? <Check size={12} /> : <span />} {active ? 'Active' : 'Not active'}</li>
                    </ol>

                    <div className="device-row__controls">
                      <label className="ui-field">Assigned patient
                        <select value={device.patient || ''} onChange={(event) => assignPatient(device, event.target.value)} disabled={busy}>
                          <option value="">Unassigned</option>
                          {patients.map((patient) => <option key={patient.id} value={patient.id}>{patient.full_name}</option>)}
                        </select>
                      </label>
                      <div className="ui-field">
                        <span>Status</span>
                        <div className="ui-segment dv-status" role="group" aria-label={`Status for ${device.device_identifier}`}>
                          {STATUSES.map((status) => (
                            <button key={status} type="button" className={device.status === status ? 'is-on' : undefined} onClick={() => changeStatus(device, status)} disabled={busy} aria-pressed={device.status === status}>{status}</button>
                          ))}
                        </div>
                      </div>
                    </div>

                    <div className="device-row__actions">
                      {canIssue && <button type="button" className="ui-btn ui-btn--soft ui-btn--sm" onClick={() => issue(device)} disabled={busy}><KeyRound size={14} /> Issue / rotate credential</button>}
                      {!device.credential_revoked && (
                        <button type="button" className={`ui-btn ui-btn--danger ui-btn--sm${confirmRevokeId === device.id ? ' is-armed' : ''}`} onClick={() => revoke(device)} disabled={busy}>
                          <ShieldOff size={14} /> {confirmRevokeId === device.id ? 'Click again to confirm' : 'Revoke credential'}
                        </button>
                      )}
                      <span className="dv-cred-state">{device.credential_revoked ? 'No active credential' : `Last used ${device.credential_last_used_at ? new Date(device.credential_last_used_at).toLocaleString() : 'never'}`}</span>
                    </div>
                  </article>
                )
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}