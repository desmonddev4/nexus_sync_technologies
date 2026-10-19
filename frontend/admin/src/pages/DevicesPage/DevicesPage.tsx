import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import {
  Boxes,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  Cpu,
  KeyRound,
  Link2,
  Lock,
  Plus,
  Radio,
  RefreshCw,
  Search,
  ShieldOff,
  Smartphone,
  UserRound,
  Watch,
  X,
  Zap,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { createRegistryDevice, getDeviceRegistry, getPatients, issueDeviceCredential, revokeDeviceCredential, updateRegistryDevice } from '../../api/operations'
import type { DeviceRegistryRecord, IssuedDeviceCredential, Patient } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { MetricTile } from '../../components/MetricTile/MetricTile'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './DevicesPage.css'

/* ------------------------------------------------------------------ */
/* Constants & helpers                                                 */
/* ------------------------------------------------------------------ */

const initialDraft = { device_identifier: '', device_type: 'simulator', patient: '', status: 'registered' }

const STATUSES = ['registered', 'active', 'inactive', 'revoked'] as const
const INITIAL_STATUSES = ['registered', 'active', 'inactive'] as const

const DEVICE_TYPES: { value: string; label: string; hint: string; icon: LucideIcon }[] = [
  { value: 'simulator', label: 'Simulator', hint: 'Test data source', icon: Cpu },
  { value: 'wearable', label: 'Wearable', hint: 'Worn by the patient', icon: Watch },
  { value: 'phone_gateway', label: 'Phone gateway', hint: 'Relays sensor data', icon: Smartphone },
  { value: 'other', label: 'Other', hint: 'Anything else', icon: Boxes },
]

const typeMeta = (value: string) => DEVICE_TYPES.find((type) => type.value === value) ?? DEVICE_TYPES[3]
const words = (value: string) => value.replaceAll('_', ' ')
const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join('') || 'P'

/* ------------------------------------------------------------------ */
/* Selection controls                                                  */
/* ------------------------------------------------------------------ */

/** Visual picker for the device type: four big tiles instead of a dropdown. */
function TypeTiles({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div className="dv-types" role="radiogroup" aria-label="Device type">
      {DEVICE_TYPES.map(({ value: type, label, hint, icon: Icon }) => (
        <button key={type} type="button" role="radio" aria-checked={value === type} className={`dv-type${value === type ? ' is-on' : ''}`} onClick={() => onChange(type)}>
          <span className="dv-type__icon"><Icon size={20} /></span>
          <strong>{label}</strong>
          <small>{hint}</small>
          <span className="dv-type__tick"><Check size={12} /></span>
        </button>
      ))}
    </div>
  )
}

/** Searchable patient picker with avatars — replaces the plain <select>. */
function PatientPicker({
  patients, value, onChange, disabled, label, compact,
}: { patients: Patient[]; value: string; onChange: (id: string) => void; disabled?: boolean; label: string; compact?: boolean }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (event: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', onPointer)
    document.addEventListener('keydown', onKey)
    searchRef.current?.focus()
    return () => {
      document.removeEventListener('mousedown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const selected = patients.find((patient) => patient.id === value)
  const needle = query.trim().toLowerCase()
  const options = patients.filter((patient) => patient.full_name.toLowerCase().includes(needle))

  function pick(id: string) {
    onChange(id)
    setOpen(false)
    setQuery('')
  }

  return (
    <div className={`pp${open ? ' is-open' : ''}${compact ? ' pp--compact' : ''}`} ref={rootRef}>
      <button type="button" className="pp-trigger" onClick={() => setOpen((current) => !current)} disabled={disabled} aria-haspopup="listbox" aria-expanded={open} aria-label={label}>
        {selected ? (
          <>
            <span className="pp-avatar">{initials(selected.full_name)}</span>
            <span className="pp-name">{selected.full_name}</span>
          </>
        ) : (
          <>
            <span className="pp-avatar pp-avatar--empty"><UserRound size={14} /></span>
            <span className="pp-name pp-name--empty">Not assigned</span>
          </>
        )}
        <ChevronDown size={16} className="pp-chevron" />
      </button>

      {open && (
        <div className="pp-pop" role="listbox" aria-label={label}>
          <div className="pp-search">
            <Search size={14} />
            <input ref={searchRef} value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search patients…" aria-label="Search patients" />
          </div>
          <ul>
            <li>
              <button type="button" role="option" aria-selected={!value} className={`pp-option${!value ? ' is-on' : ''}`} onClick={() => pick('')}>
                <span className="pp-avatar pp-avatar--empty"><X size={13} /></span>
                <span>Not assigned</span>
                {!value && <Check size={15} />}
              </button>
            </li>
            {options.map((patient) => (
              <li key={patient.id}>
                <button type="button" role="option" aria-selected={patient.id === value} className={`pp-option${patient.id === value ? ' is-on' : ''}`} onClick={() => pick(patient.id)}>
                  <span className="pp-avatar">{initials(patient.full_name)}</span>
                  <span>{patient.full_name}</span>
                  {patient.id === value && <Check size={15} />}
                </button>
              </li>
            ))}
            {options.length === 0 && <li className="pp-none">No patients found</li>}
          </ul>
        </div>
      )}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

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
  const [typeFilter, setTypeFilter] = useState('all')
  const [confirmRevokeId, setConfirmRevokeId] = useState('')
  const [secretCopied, setSecretCopied] = useState(false)
  const [copiedId, setCopiedId] = useState('')

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

  async function copyIdentifier(device: DeviceRegistryRecord) {
    try {
      await navigator.clipboard.writeText(device.device_identifier)
      setCopiedId(device.id)
      window.setTimeout(() => setCopiedId((current) => (current === device.id ? '' : current)), 1500)
    } catch { /* clipboard unavailable */ }
  }

  /* ------------------------------ derived ------------------------------ */

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const device of devices) counts.set(device.status, (counts.get(device.status) ?? 0) + 1)
    return counts
  }, [devices])

  const typesPresent = useMemo(() => [...new Set(devices.map((device) => device.device_type))], [devices])

  const needle = query.trim().toLowerCase()
  const visible = devices.filter((device) =>
    (statusFilter === 'all' || device.status === statusFilter) &&
    (typeFilter === 'all' || device.device_type === typeFilter) &&
    (!needle || `${device.device_identifier} ${device.device_type}`.toLowerCase().includes(needle)),
  )

  const patientName = (id: string | null) => patients.find((patient) => patient.id === id)?.full_name

  const activeCount = statusCounts.get('active') ?? 0
  const unassignedCount = devices.filter((device) => !device.patient).length
  const neverConnected = devices.filter((device) => !device.last_seen_at).length

  /* ------------------------------ render ------------------------------ */

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
          <div className="dv-credential__icon"><KeyRound size={22} /></div>
          <div className="dv-credential__body">
            <strong>Credential shown once</strong>
            <p>{issued.warning} Never paste it into chat or commit it.</p>
            <code>{issued.secret}</code>
          </div>
          <div className="dv-credential__actions">
            <button type="button" className={`ui-btn ui-btn--sm${secretCopied ? ' is-copied' : ''}`} onClick={copySecret}>
              {secretCopied ? <Check size={15} /> : <Copy size={15} />} {secretCopied ? 'Copied' : 'Copy secret'}
            </button>
            <button type="button" className="ui-btn ui-btn--ghost ui-btn--sm" onClick={() => setIssued(null)}><X size={14} /> Dismiss</button>
          </div>
        </section>
      )}

      {/* ---------- Summary ---------- */}
      {!loading && (
        <section className="dv-metrics" aria-label="Device summary">
          <MetricTile label="Registered devices" value={devices.length} detail="In the registry" icon={Cpu} tone="blue" />
          <MetricTile label="Active" value={activeCount} detail="Can send data" icon={Zap} tone="green" />
          <MetricTile label="Unassigned" value={unassignedCount} detail="Not linked to a patient" icon={Link2} tone="amber" />
          <MetricTile label="Never connected" value={neverConnected} detail="No data received yet" icon={Radio} tone="coral" />
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
            <label className="ui-field">Device identifier
              <input required maxLength={100} value={draft.device_identifier} onChange={(event) => setDraft({ ...draft, device_identifier: event.target.value })} placeholder="e.g. NS-WEARABLE-001" />
            </label>

            <div className="ui-field">
              <span>Type</span>
              <TypeTiles value={draft.device_type} onChange={(device_type) => setDraft({ ...draft, device_type })} />
            </div>

            <div className="ui-field">
              <span>Patient assignment</span>
              <PatientPicker patients={patients} value={draft.patient} onChange={(patient) => setDraft({ ...draft, patient })} label="Patient assignment" />
            </div>

            <div className="ui-field">
              <span>Initial status</span>
              <div className="ui-segment dv-initial" role="group" aria-label="Initial status">
                {INITIAL_STATUSES.map((status) => (
                  <button key={status} type="button" className={draft.status === status ? 'is-on' : undefined} onClick={() => setDraft({ ...draft, status })} aria-pressed={draft.status === status}>{status}</button>
                ))}
              </div>
            </div>

            <button className={`ui-btn dv-submit${busyId === 'new' ? ' is-busy' : ''}`} type="submit" disabled={busyId === 'new'}>
              <Plus size={16} /> {busyId === 'new' ? 'Registering…' : 'Register device'}
            </button>
          </form>
        </section>

        {/* ---------- Registry ---------- */}
        <section className="ui-panel device-list-panel">
          <div className="ui-panel__head">
            <h2><span className="ui-panel__icon"><Watch size={16} /></span> Registered devices</h2>
            <span className="ui-tag">{visible.length} shown</span>
          </div>
          <p className="ui-muted dv-hint">Secrets are never listed or stored in plaintext.</p>

          <div className="dv-controls">
            <div className="ui-search">
              <Search size={16} />
              <input aria-label="Search devices" placeholder="Search identifier or type…" value={query} onChange={(event) => setQuery(event.target.value)} />
              {query && <button type="button" className="ui-search__clear" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}
            </div>

            <div className="dv-chips" role="group" aria-label="Filter by status">
              <button type="button" className={`ui-chip${statusFilter === 'all' ? ' is-on' : ''}`} onClick={() => setStatusFilter('all')} aria-pressed={statusFilter === 'all'}>All status <em>{devices.length}</em></button>
              {STATUSES.filter((status) => statusCounts.has(status)).map((status) => (
                <button key={status} type="button" className={`ui-chip dv-chip--${status}${statusFilter === status ? ' is-on' : ''}`} onClick={() => setStatusFilter(status)} aria-pressed={statusFilter === status}>
                  <i className="dv-dot" /> {status} <em>{statusCounts.get(status)}</em>
                </button>
              ))}
            </div>

            {typesPresent.length > 1 && (
              <div className="dv-chips" role="group" aria-label="Filter by type">
                <button type="button" className={`ui-chip${typeFilter === 'all' ? ' is-on' : ''}`} onClick={() => setTypeFilter('all')} aria-pressed={typeFilter === 'all'}>All types</button>
                {typesPresent.map((type) => {
                  const { icon: Icon, label } = typeMeta(type)
                  return (
                    <button key={type} type="button" className={`ui-chip${typeFilter === type ? ' is-on' : ''}`} onClick={() => setTypeFilter(type)} aria-pressed={typeFilter === type}><Icon size={13} /> {label}</button>
                  )
                })}
              </div>
            )}
          </div>

          {loading ? (
            <div className="ui-skeleton-stack" aria-busy="true"><div className="ui-skeleton" style={{ height: 190 }} /><div className="ui-skeleton" style={{ height: 190 }} /></div>
          ) : visible.length === 0 ? (
            devices.length === 0
              ? <EmptyState icon={Cpu} title="No registered devices yet" detail="Register a device on the left to start the provisioning flow." />
              : <EmptyState icon={Search} title="No matching devices" detail="No devices match the current search or filters." />
          ) : (
            <div className="device-list">
              {visible.map((device, index) => {
                const meta = typeMeta(device.device_type)
                const Icon = meta.icon
                const linked = Boolean(device.patient)
                const active = device.status === 'active'
                const eligibleType = ['wearable', 'simulator'].includes(device.device_type)
                const canIssue = active && linked && eligibleType
                const busy = busyId === device.id
                const lockedReason = !linked ? 'Link a patient first' : !active ? 'Activate the device first' : 'Wearables and simulators only'

                return (
                  <article className={`device-row dv-status-${device.status}${busy ? ' is-busy' : ''}`} key={device.id} style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}>
                    <div className="device-row__head">
                      <span className="dv-type-icon"><Icon size={20} /></span>
                      <div>
                        <strong>
                          {device.device_identifier}
                          <button type="button" className="dv-copy" onClick={() => copyIdentifier(device)} aria-label={`Copy identifier ${device.device_identifier}`} title="Copy identifier">
                            {copiedId === device.id ? <Check size={13} /> : <Copy size={13} />}
                          </button>
                        </strong>
                        <small>{words(device.device_type)} · {device.last_seen_at ? `last seen ${new Date(device.last_seen_at).toLocaleString()}` : 'never connected'}</small>
                      </div>
                      <StatusBadge value={device.status} />
                    </div>

                    {/* Provisioning track */}
                    <ol className="dv-track" aria-label="Provisioning progress">
                      <li className="is-done"><span className="dv-node"><Check size={13} /></span><strong>Registered</strong><small>In registry</small></li>
                      <li className={linked ? 'is-done' : undefined}><span className="dv-node">{linked ? <Check size={13} /> : <Link2 size={13} />}</span><strong>{linked ? 'Linked' : 'Link patient'}</strong><small>{linked ? (patientName(device.patient) ?? 'Patient') : 'Not linked'}</small></li>
                      <li className={active ? 'is-done' : undefined}><span className="dv-node">{active ? <Check size={13} /> : <Zap size={13} />}</span><strong>{active ? 'Active' : 'Activate'}</strong><small>{active ? 'Can send data' : `Status: ${device.status}`}</small></li>
                      <li className={canIssue ? 'is-ready' : 'is-locked'}><span className="dv-node">{canIssue ? <KeyRound size={13} /> : <Lock size={13} />}</span><strong>{canIssue ? 'Ready' : 'Credential'}</strong><small>{canIssue ? 'Can issue credential' : lockedReason}</small></li>
                    </ol>

                    <div className="device-row__controls">
                      <div className="ui-field">
                        <span>Assigned patient</span>
                        <PatientPicker compact patients={patients} value={device.patient || ''} onChange={(patientId) => assignPatient(device, patientId)} disabled={busy} label={`Assigned patient for ${device.device_identifier}`} />
                      </div>
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
                      <Link className="ui-btn ui-btn--sm" to={`/devices/${device.id}`}>
                        View device
                      </Link>
                      {canIssue && <button type="button" className="ui-btn dv-issue ui-btn--sm" onClick={() => issue(device)} disabled={busy}><KeyRound size={15} /> Issue / rotate credential</button>}
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