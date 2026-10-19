import { useEffect, useMemo, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { ArrowUpRight, CalendarDays, ChevronDown, LayoutGrid, List, Phone, Search, UserPlus, UserRound, X } from 'lucide-react'
import { Link } from 'react-router-dom'
import { createPatient, getPatientDevices, getPatients } from '../../api/operations'
import type { DeviceHealth, Patient } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './PatientsPage.css'

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

const PAGE_SIZE = 24

type ViewMode = 'list' | 'grid'
type SortMode = 'name' | 'newest'

const words = (value: string) => value.replaceAll('_', ' ')

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'P'
  )
}

/** Stable accent for each patient's avatar, picked from the brand palette. */
function toneOf(id: string) {
  let sum = 0
  for (let i = 0; i < id.length; i += 1) sum += id.charCodeAt(i)
  return sum % 4
}

function Highlight({ text, query }: { text: string; query: string }) {
  const needle = query.trim().toLowerCase()
  if (!needle) return <>{text}</>
  const index = text.toLowerCase().indexOf(needle)
  if (index < 0) return <>{text}</>
  return (
    <>
      {text.slice(0, index)}
      <mark>{text.slice(index, index + needle.length)}</mark>
      {text.slice(index + needle.length)}
    </>
  )
}

function PatientItem({ patient, query, view, index, devices }: { patient: Patient; query: string; view: ViewMode; index: number; devices: DeviceHealth[] }) {
  const shortId = patient.id.slice(0, 8)
  const primaryDevice = devices[0]
  const deviceStatusClass = primaryDevice ? `patient-device__status--${primaryDevice.status.toLowerCase()}` : 'patient-device__status--none'
  const lastSeen = primaryDevice?.last_seen_at ? new Date(primaryDevice.last_seen_at).toLocaleString() : 'Awaiting first heartbeat'

  return (
    <article className={`patient-row patient-row--${view}`} style={{ animationDelay: `${Math.min(index, 12) * 35}ms` }}>
      <span className={`patient-avatar patient-avatar--${toneOf(patient.id)}`} aria-hidden="true">{initials(patient.full_name)}</span>

      <div className="patient-main">
        <strong>
          <Link className="patient-link" to={`/patients/${patient.id}`}>
            <Highlight text={patient.full_name} query={query} />
          </Link>
        </strong>
        <small>ID <Highlight text={shortId} query={query} /></small>
      </div>

      <div className="patient-contact">
        {patient.phone_number ? (
          <a className="patient-phone" href={`tel:${patient.phone_number}`}>
            <Phone size={13} /> <Highlight text={patient.phone_number} query={query} />
          </a>
        ) : (
          <span className="patient-phone patient-phone--none"><Phone size={13} /> No phone on record</span>
        )}
        <small><CalendarDays size={12} /> {patient.date_of_birth ? `DOB ${patient.date_of_birth}` : 'DOB not recorded'}</small>
      </div>

      <div className="patient-device">
        {primaryDevice ? (
          <>
            <div className="patient-device__meta">
              <span className="patient-device__label">{primaryDevice.device_identifier}</span>
              <span className={`patient-device__status ${deviceStatusClass}`}>{primaryDevice.status}</span>
            </div>
            <small>
              {primaryDevice.device_type} · {primaryDevice.battery_percent ?? 'n/a'}% battery · {lastSeen}
            </small>
          </>
        ) : (
          <div className="patient-device__meta">
            <span className="patient-device__empty">No wearable linked</span>
          </div>
        )}
      </div>

      <StatusBadge value={patient.status} />

      <Link className="patient-open" to={`/patients/${patient.id}`} aria-label={`Open ${patient.full_name}`}>
        <span>Open record</span>
        <ArrowUpRight size={15} />
      </Link>
    </article>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [devicesByPatient, setDevicesByPatient] = useState<Record<string, DeviceHealth[]>>({})
  const [query, setQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [sort, setSort] = useState<SortMode>('name')
  const [view, setView] = useState<ViewMode>('list')
  const [limit, setLimit] = useState(PAGE_SIZE)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showEnrollment, setShowEnrollment] = useState(false)
  const [savingPatient, setSavingPatient] = useState(false)
  const [newPatient, setNewPatient] = useState({ full_name: '', date_of_birth: '', phone_number: '', relevant_medical_notes: '' })
  const searchRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let active = true

    getPatients()
      .then(async (nextPatients) => {
        if (!active) return
        setPatients(nextPatients)

        const entries = await Promise.all(
          nextPatients.map(async (patient) => {
            try {
              const devices = await getPatientDevices(patient.id)
              return [patient.id, devices] as const
            } catch {
              return [patient.id, []] as const
            }
          }),
        )

        if (!active) return
        setDevicesByPatient(Object.fromEntries(entries))
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
  }, [])

  async function submitNewPatient(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setSavingPatient(true)
    setError('')
    try {
      const created = await createPatient({
        full_name: newPatient.full_name.trim(),
        phone_number: newPatient.phone_number.trim(),
        date_of_birth: newPatient.date_of_birth || null,
        relevant_medical_notes: newPatient.relevant_medical_notes.trim(),
        status: 'active',
      })
      setPatients((current) => [created, ...current])
      setNewPatient({ full_name: '', date_of_birth: '', phone_number: '', relevant_medical_notes: '' })
      setShowEnrollment(false)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Unable to create patient record.')
    } finally {
      setSavingPatient(false)
    }
  }

  // Press "/" anywhere on the page to jump to search.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null
      const typing = target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)
      if (event.key === '/' && !typing && !event.metaKey && !event.ctrlKey) {
        event.preventDefault()
        searchRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const statusCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const patient of patients) counts.set(patient.status, (counts.get(patient.status) ?? 0) + 1)
    return [...counts.entries()].sort((a, b) => b[1] - a[1])
  }, [patients])

  const needle = query.trim().toLowerCase()
  const filtered = useMemo(() => {
    const rows = patients.filter(
      (patient) =>
        (statusFilter === 'all' || patient.status === statusFilter) &&
        (!needle || `${patient.full_name} ${patient.id} ${patient.phone_number ?? ''}`.toLowerCase().includes(needle)),
    )
    return rows.sort((a, b) =>
      sort === 'name'
        ? a.full_name.localeCompare(b.full_name)
        : Date.parse(b.created_at) - Date.parse(a.created_at),
    )
  }, [patients, statusFilter, needle, sort])

  const visible = filtered.slice(0, limit)
  const filtersActive = Boolean(needle) || statusFilter !== 'all'

  function changeQuery(value: string) {
    setQuery(value)
    setLimit(PAGE_SIZE)
  }

  function clearFilters() {
    setQuery('')
    setStatusFilter('all')
    setLimit(PAGE_SIZE)
    searchRef.current?.focus()
  }

  return (
    <div className="patients-page">
      {/* ---------- Header ---------- */}
      <header className="pt-head">
        <div>
          <h1>Patient directory</h1>
          <p>Access is limited to records permitted by your role.</p>
        </div>
        <div className="pt-head__actions">
          <span className="patients-count"><strong>{patients.length}</strong> records</span>
          <button type="button" className="pt-enroll-button" onClick={() => setShowEnrollment((value) => !value)} aria-expanded={showEnrollment}>
            <UserPlus size={16} /> {showEnrollment ? 'Close form' : 'Enroll patient'}
          </button>
        </div>
      </header>

      {showEnrollment && (
        <form className="pt-enrollment" onSubmit={submitNewPatient}>
          <div><p className="page-eyebrow">STAFF WORKFLOW</p><h2>New patient record</h2><p>Create the patient record first; then link a patient account and assign devices from their respective administration pages.</p></div>
          <label>Full name<input required maxLength={200} value={newPatient.full_name} onChange={(event) => setNewPatient({ ...newPatient, full_name: event.target.value })} /></label>
          <label>Phone number<input type="tel" value={newPatient.phone_number} onChange={(event) => setNewPatient({ ...newPatient, phone_number: event.target.value })} /></label>
          <label>Date of birth<input type="date" value={newPatient.date_of_birth} onChange={(event) => setNewPatient({ ...newPatient, date_of_birth: event.target.value })} /></label>
          <label className="pt-enrollment__notes">Relevant medical notes<textarea rows={3} value={newPatient.relevant_medical_notes} onChange={(event) => setNewPatient({ ...newPatient, relevant_medical_notes: event.target.value })} /></label>
          <div className="pt-enrollment__footer"><span>Only enter information required for the intended care workflow.</span><button type="submit" disabled={savingPatient}>{savingPatient ? 'Saving…' : 'Create patient record'}</button></div>
        </form>
      )}

      {/* ---------- Search ---------- */}
      <div className="patient-search">
        <Search size={18} aria-hidden="true" />
        <input
          ref={searchRef}
          aria-label="Search patients"
          placeholder="Search name, phone, or identifier…"
          value={query}
          onChange={(event) => changeQuery(event.target.value)}
          onKeyDown={(event) => { if (event.key === 'Escape') changeQuery('') }}
        />
        {query ? (
          <button type="button" className="patient-search__clear" onClick={() => changeQuery('')} aria-label="Clear search">
            <X size={15} />
          </button>
        ) : (
          <kbd aria-hidden="true">/</kbd>
        )}
      </div>

      {/* ---------- Filters & view controls ---------- */}
      {!loading && patients.length > 0 && (
        <div className="pt-controls">
          <div className="pt-chips" role="group" aria-label="Filter by status">
            <button type="button" className={`pt-chip${statusFilter === 'all' ? ' is-on' : ''}`} onClick={() => { setStatusFilter('all'); setLimit(PAGE_SIZE) }} aria-pressed={statusFilter === 'all'}>
              All <em>{patients.length}</em>
            </button>
            {statusCounts.map(([status, count]) => (
              <button key={status} type="button" className={`pt-chip${statusFilter === status ? ' is-on' : ''}`} onClick={() => { setStatusFilter(status); setLimit(PAGE_SIZE) }} aria-pressed={statusFilter === status}>
                {words(status)} <em>{count}</em>
              </button>
            ))}
          </div>

          <div className="pt-tools">
            <div className="pt-segment" role="group" aria-label="Sort order">
              <button type="button" className={sort === 'name' ? 'is-on' : undefined} onClick={() => setSort('name')} aria-pressed={sort === 'name'}>A–Z</button>
              <button type="button" className={sort === 'newest' ? 'is-on' : undefined} onClick={() => setSort('newest')} aria-pressed={sort === 'newest'}>Newest</button>
            </div>
            <div className="pt-segment pt-segment--icons" role="group" aria-label="Layout">
              <button type="button" className={view === 'list' ? 'is-on' : undefined} onClick={() => setView('list')} aria-pressed={view === 'list'} aria-label="List view" title="List view"><List size={15} /></button>
              <button type="button" className={view === 'grid' ? 'is-on' : undefined} onClick={() => setView('grid')} aria-pressed={view === 'grid'} aria-label="Card view" title="Card view"><LayoutGrid size={15} /></button>
            </div>
          </div>
        </div>
      )}

      {error && <div className="page-error" role="alert">Unable to load patients: {error}</div>}

      {/* ---------- Results ---------- */}
      {loading ? (
        <div className={`patient-list patient-list--${view}`} aria-busy="true" aria-label="Loading patient records">
          {Array.from({ length: 6 }, (_, index) => <div className="pt-skeleton" key={index} />)}
        </div>
      ) : visible.length === 0 ? (
        <div className="pt-empty">
          <EmptyState
            icon={UserRound}
            title={filtersActive ? 'No matching patients' : 'No patient records'}
            detail={filtersActive ? 'No records match the current search or filter.' : 'Patient records permitted by your role will appear here.'}
          />
          {filtersActive && <button type="button" className="pt-reset" onClick={clearFilters}>Clear search and filters</button>}
        </div>
      ) : (
        <>
          <p className="pt-summary" aria-live="polite">
            Showing <strong>{visible.length}</strong> of <strong>{filtered.length}</strong>
            {filtersActive ? ' matching' : ''} patients
          </p>
          <div className={`patient-list patient-list--${view}`}>
            {visible.map((patient, index) => (
              <PatientItem key={patient.id} patient={patient} query={query} view={view} index={index} devices={devicesByPatient[patient.id] ?? []} />
            ))}
          </div>
          {filtered.length > visible.length && (
            <button type="button" className="pt-more" onClick={() => setLimit((value) => value + PAGE_SIZE)}>
              Show {Math.min(PAGE_SIZE, filtered.length - visible.length)} more <ChevronDown size={16} />
            </button>
          )}
        </>
      )}
    </div>
  )
}