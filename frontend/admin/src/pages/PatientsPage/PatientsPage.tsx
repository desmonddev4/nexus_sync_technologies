import { useEffect, useState } from 'react'
import { ArrowUpRight, Search, UserRound } from 'lucide-react'
import { Link } from 'react-router-dom'
import { getPatients } from '../../api/operations'
import type { Patient } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './PatientsPage.css'

export function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([])
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getPatients().then(setPatients).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false))
  }, [])

  const visible = patients.filter((patient) => `${patient.full_name} ${patient.id} ${patient.phone_number}`.toLowerCase().includes(query.toLowerCase()))

  return (
    <div className="patients-page">
      <header className="page-heading"><div><p className="page-eyebrow">OPERATIONS / PATIENTS</p><h1>Patient directory</h1><p className="page-subtitle">Access is limited to records permitted by your role.</p></div><span className="patients-count">{patients.length} records</span></header>
      <div className="patient-search"><Search size={16} /><input aria-label="Search patients" placeholder="Search name, phone, or identifier…" value={query} onChange={(event) => setQuery(event.target.value)} /></div>
      {error && <div className="page-error" role="alert">Unable to load patients: {error}</div>}
      {loading ? <div className="loading-row">Loading patient records…</div> : visible.length === 0 ? <EmptyState icon={UserRound} title="No patient records" detail="No records match the current search." /> : (
        <div className="patient-list">{visible.map((patient) => <article className="patient-row" key={patient.id}>
          <span className="patient-avatar"><UserRound size={17} /></span>
          <div className="patient-main"><strong><Link className="patient-link" to={`/patients/${patient.id}`}>{patient.full_name}</Link></strong><small>Patient ID · {patient.id.slice(0, 8)}</small></div>
          <div className="patient-contact"><span>{patient.phone_number || 'No phone on record'}</span><small>{patient.date_of_birth ? `DOB ${patient.date_of_birth}` : 'DOB not recorded'}</small></div>
          <StatusBadge value={patient.status} />
          <Link className="row-open" to={`/patients/${patient.id}`} aria-label="Open patient"><ArrowUpRight size={15} /></Link>
        </article>)}</div>
      )}
    </div>
  )
}