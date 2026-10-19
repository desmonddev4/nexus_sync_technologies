import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Ambulance, Building2, CheckCircle2, MapPin, Phone, Plus, RadioTower, Search, X } from 'lucide-react'
import {
  createManagedFacility,
  createManagedProvider,
  createManagedVehicle,
  getFacilities,
  getManagedFacilities,
  getManagedProviders,
  getManagedVehicles,
  getProviders,
  getVehicles,
  verifyManagedFacility,
  verifyManagedProvider,
} from '../../api/operations'
import type {
  EmergencyProvider,
  FacilityDirectoryRecord,
  HealthcareFacility,
  NearbyVehicle,
  ProviderDirectoryRecord,
  VehicleDirectoryRecord,
} from '../../types/api'
import { useAuth } from '../../auth/useAuth'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { MetricTile } from '../../components/MetricTile/MetricTile'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './ServicesPage.css'

type Tab = 'providers' | 'facilities' | 'vehicles'
const words = (value: string) => value.replaceAll('_', ' ')

export function ServicesPage() {
  const { user } = useAuth()
  const canManage = user?.role === 'emergency_coordinator' || user?.role === 'superuser'
  const [providers, setProviders] = useState<EmergencyProvider[]>([])
  const [facilities, setFacilities] = useState<HealthcareFacility[]>([])
  const [vehicles, setVehicles] = useState<NearbyVehicle[]>([])
  const [managedProviders, setManagedProviders] = useState<ProviderDirectoryRecord[]>([])
  const [managedFacilities, setManagedFacilities] = useState<FacilityDirectoryRecord[]>([])
  const [managedVehicles, setManagedVehicles] = useState<VehicleDirectoryRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [managementError, setManagementError] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [tab, setTab] = useState<Tab>('providers')
  const [query, setQuery] = useState('')
  const [verificationSources, setVerificationSources] = useState<Record<string, string>>({})
  const [draft, setDraft] = useState({
    provider_name: '', provider_type: 'private_ambulance', dispatch_phone_number: '', provider_address: '', coverage_description: '',
    facility_name: '', facility_type: 'clinic', facility_address: '', facility_phone: '', facility_latitude: '', facility_longitude: '',
    vehicle_identifier: '', vehicle_provider: '', vehicle_capabilities: '',
  })

  async function loadManagement() {
    const [providerRows, facilityRows, vehicleRows, operationalProviders, operationalFacilities, operationalVehicles] = await Promise.all([
      getManagedProviders(), getManagedFacilities(), getManagedVehicles(),
      getProviders(), getFacilities(), getVehicles(),
    ])
    setManagedProviders(providerRows)
    setManagedFacilities(facilityRows)
    setManagedVehicles(vehicleRows)
    setProviders(operationalProviders)
    setFacilities(operationalFacilities)
    setVehicles(operationalVehicles)
    if (!draft.vehicle_provider && providerRows.length) {
      setDraft((current) => ({ ...current, vehicle_provider: providerRows[0].id }))
    }
  }

  useEffect(() => {
    let active = true
    const directoryRequests = canManage
      ? [getManagedProviders(), getManagedFacilities(), getManagedVehicles()]
      : []
    Promise.all([getProviders(), getFacilities(), getVehicles(), ...directoryRequests])
      .then(([providerRows, facilityRows, vehicleRows, managedProviderRows, managedFacilityRows, managedVehicleRows]) => {
        if (!active) return
        setProviders(providerRows as EmergencyProvider[])
        setFacilities(facilityRows as HealthcareFacility[])
        setVehicles(vehicleRows as NearbyVehicle[])
        if (canManage) {
          const allProviders = managedProviderRows as ProviderDirectoryRecord[]
          setManagedProviders(allProviders)
          setManagedFacilities(managedFacilityRows as FacilityDirectoryRecord[])
          setManagedVehicles(managedVehicleRows as VehicleDirectoryRecord[])
          if (allProviders.length) setDraft((current) => ({ ...current, vehicle_provider: current.vehicle_provider || allProviders[0].id }))
        }
      })
      .catch((reason: Error) => { if (active) setError(reason.message) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [canManage])

  const needle = query.trim().toLowerCase()
  const match = (...parts: (string | null | undefined)[]) => !needle || parts.join(' ').toLowerCase().includes(needle)
  const shown = useMemo(() => ({
    providers: providers.filter((provider) => match(provider.name, provider.provider_type, provider.coverage_description, provider.dispatch_phone_number)),
    facilities: facilities.filter((facility) => match(facility.name, facility.facility_type, facility.address, facility.phone_number)),
    vehicles: vehicles.filter((vehicle) => match(vehicle.vehicle_identifier, vehicle.provider_name)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [providers, facilities, vehicles, needle])

  async function createRecord(event: FormEvent<HTMLFormElement>, kind: 'provider' | 'facility' | 'vehicle') {
    event.preventDefault()
    setBusy(true)
    setManagementError('')
    setMessage('')
    try {
      if (kind === 'provider') {
        await createManagedProvider({
          name: draft.provider_name.trim(), provider_type: draft.provider_type,
          dispatch_phone_number: draft.dispatch_phone_number.trim(), address: draft.provider_address.trim(),
          coverage_description: draft.coverage_description.trim(),
        })
      } else if (kind === 'facility') {
        await createManagedFacility({
          name: draft.facility_name.trim(), facility_type: draft.facility_type,
          address: draft.facility_address.trim(), phone_number: draft.facility_phone.trim(),
          latitude: draft.facility_latitude, longitude: draft.facility_longitude,
        })
      } else {
        await createManagedVehicle({
          provider: draft.vehicle_provider, vehicle_identifier: draft.vehicle_identifier.trim(),
          capabilities: draft.vehicle_capabilities.split(',').map((item) => item.trim()).filter(Boolean),
          data_source: 'simulator', availability: 'unavailable',
        })
      }
      await loadManagement()
      setMessage(kind === 'vehicle'
        ? 'Simulated vehicle registered as unavailable under a simulation-only provider.'
        : `${kind[0].toUpperCase()}${kind.slice(1)} created and remains unverified until independently checked.`)
      setDraft((current) => ({
        ...current, provider_name: '', dispatch_phone_number: '', provider_address: '', coverage_description: '',
        facility_name: '', facility_address: '', facility_phone: '', facility_latitude: '', facility_longitude: '',
        vehicle_identifier: '', vehicle_capabilities: '',
      }))
    } catch (reason) {
      setManagementError(reason instanceof Error ? reason.message : `Unable to create ${kind} record.`)
    } finally { setBusy(false) }
  }

  async function verifyRecord(kind: 'provider' | 'facility', id: string) {
    const source = verificationSources[`${kind}:${id}`]?.trim()
    if (!source) { setManagementError('Enter a verification source or reference first.'); return }
    setBusy(true)
    setManagementError('')
    setMessage('')
    try {
      if (kind === 'provider') await verifyManagedProvider(id, source)
      else await verifyManagedFacility(id, source)
      await loadManagement()
      setMessage('Verification was recorded and audited. It does not authorize a live vehicle feed.')
    } catch (reason) { setManagementError(reason instanceof Error ? reason.message : 'Unable to verify record.') }
    finally { setBusy(false) }
  }

  const tabs: { key: Tab; label: string; icon: typeof RadioTower; total: number }[] = [
    { key: 'providers', label: 'Providers', icon: RadioTower, total: providers.length },
    { key: 'facilities', label: 'Facilities', icon: Building2, total: facilities.length },
    { key: 'vehicles', label: 'Vehicles', icon: Ambulance, total: vehicles.length },
  ]

  return (
    <div className="ui-page services-page">
      <header className="ui-head"><div><h1>Emergency services</h1><p>Operational lists include only verified providers and facilities.</p></div></header>
      {error && <div className="ui-error" role="alert">Unable to load directory: {error}</div>}
      {loading ? <div className="ui-skeleton-stack" aria-busy="true"><div className="ui-skeleton" /><div className="ui-skeleton" /></div> : <>
        <section className="srv-metrics" aria-label="Directory summary">
          <MetricTile label="Providers" value={providers.length} detail="Verified response network" icon={RadioTower} tone="blue" />
          <MetricTile label="Facilities" value={facilities.length} detail="Verified receiving facilities" icon={Building2} tone="green" />
          <MetricTile label="Vehicles" value={vehicles.length} detail="Operationally eligible feed" icon={Ambulance} tone="amber" />
        </section>
        <section className="ui-toolbar">
          <div className="ui-segment" role="tablist" aria-label="Directory section">{tabs.map(({ key, label, icon: Icon, total }) => <button key={key} type="button" role="tab" aria-selected={tab === key} className={tab === key ? 'is-on' : undefined} onClick={() => setTab(key)}><Icon size={15} /> {label} <em>{total}</em></button>)}</div>
          <div className="ui-search"><Search size={16} /><input aria-label="Search directory" placeholder="Search this directory…" value={query} onChange={(event) => setQuery(event.target.value)} />{query && <button type="button" onClick={() => setQuery('')} aria-label="Clear search"><X size={14} /></button>}</div>
        </section>
        <section className="srv-grid" key={tab}>
          {shown[tab].length === 0 && <div className="ui-panel srv-empty"><EmptyState icon={tab === 'providers' ? RadioTower : tab === 'facilities' ? Building2 : Ambulance} title={`No ${tab}`} detail="Verified operational records will appear here." /></div>}
          {tab === 'providers' && shown.providers.map((provider) => <article className="srv-card" key={provider.id}><header><span className="srv-card__icon"><RadioTower size={18} /></span><div><strong>{provider.name}</strong><small>{words(provider.provider_type)}</small></div><StatusBadge value={provider.verification_status} /></header><ul><li><Phone size={14} />{provider.dispatch_phone_number ? <a href={`tel:${provider.dispatch_phone_number}`}>Dispatch {provider.dispatch_phone_number}</a> : <span>No dispatch number recorded</span>}</li><li><MapPin size={14} /><span>{provider.coverage_description || 'Coverage not recorded'}</span></li></ul></article>)}
          {tab === 'facilities' && shown.facilities.map((facility) => <article className="srv-card" key={facility.id}><header><span className="srv-card__icon srv-card__icon--green"><Building2 size={18} /></span><div><strong>{facility.name}</strong><small>{facility.facility_type}</small></div><StatusBadge value={facility.verification_status} /></header><ul><li><MapPin size={14} /><span>{facility.address || 'Address not recorded'}</span></li><li><Phone size={14} />{facility.phone_number || 'No phone recorded'}</li><li className="ui-mono srv-coords">{facility.latitude}, {facility.longitude}</li></ul></article>)}
          {tab === 'vehicles' && shown.vehicles.map((vehicle) => <article className="srv-card" key={vehicle.id}><header><span className="srv-card__icon srv-card__icon--amber"><Ambulance size={18} /></span><div><strong>{vehicle.vehicle_identifier}</strong><small>{vehicle.provider_name}</small></div><StatusBadge value={vehicle.is_simulated ? 'simulated' : vehicle.availability} /></header><ul><li><span>{vehicle.capabilities.join(', ') || 'Capability not recorded'}</span></li><li><span>{vehicle.location_updated_at ? `Updated ${new Date(vehicle.location_updated_at).toLocaleString()}` : 'Location time unknown'}</span></li>{vehicle.is_simulated && <li><small className="simulated-copy">Simulation only — not a real ambulance.</small></li>}</ul></article>)}
        </section>

        {canManage && <section className="directory-admin">
          <header><p className="page-eyebrow">COORDINATOR WORKFLOW</p><h2>Directory administration</h2><p>Create pending records. Verification is an explicit audited action; live fleet authorization is separate.</p></header>
          {managementError && <div className="ui-error" role="alert">{managementError}</div>}
          {message && <div className="directory-message" role="status">{message}</div>}
          <div className="directory-create-grid">
            <details><summary><Plus size={15} /> Add provider</summary><form onSubmit={(event) => createRecord(event, 'provider')}>
              <label>Provider name<input required value={draft.provider_name} onChange={(event) => setDraft({ ...draft, provider_name: event.target.value })} /></label>
              <label>Type<select value={draft.provider_type} onChange={(event) => setDraft({ ...draft, provider_type: event.target.value })}><option value="national_ambulance">National ambulance</option><option value="private_ambulance">Private ambulance</option></select></label>
              <label>Dispatch phone<input value={draft.dispatch_phone_number} onChange={(event) => setDraft({ ...draft, dispatch_phone_number: event.target.value })} /></label>
              <label>Address<input value={draft.provider_address} onChange={(event) => setDraft({ ...draft, provider_address: event.target.value })} /></label>
              <label>Coverage notes<textarea value={draft.coverage_description} onChange={(event) => setDraft({ ...draft, coverage_description: event.target.value })} /></label>
              <button disabled={busy}>Create pending provider</button></form></details>
            <details><summary><Plus size={15} /> Add facility</summary><form onSubmit={(event) => createRecord(event, 'facility')}>
              <label>Facility name<input required value={draft.facility_name} onChange={(event) => setDraft({ ...draft, facility_name: event.target.value })} /></label>
              <label>Type<select value={draft.facility_type} onChange={(event) => setDraft({ ...draft, facility_type: event.target.value })}><option value="clinic">Clinic</option><option value="hospital">Hospital</option><option value="other">Other</option></select></label>
              <label>Address<input value={draft.facility_address} onChange={(event) => setDraft({ ...draft, facility_address: event.target.value })} /></label>
              <label>Phone<input value={draft.facility_phone} onChange={(event) => setDraft({ ...draft, facility_phone: event.target.value })} /></label>
              <div className="directory-coordinates"><label>Latitude<input required type="number" step="any" min="-90" max="90" value={draft.facility_latitude} onChange={(event) => setDraft({ ...draft, facility_latitude: event.target.value })} /></label><label>Longitude<input required type="number" step="any" min="-180" max="180" value={draft.facility_longitude} onChange={(event) => setDraft({ ...draft, facility_longitude: event.target.value })} /></label></div>
              <button disabled={busy}>Create pending facility</button></form></details>
            <details><summary><Plus size={15} /> Add simulated vehicle</summary><form onSubmit={(event) => createRecord(event, 'vehicle')}>
              <label>Simulation-only provider<select required value={draft.vehicle_provider} onChange={(event) => setDraft({ ...draft, vehicle_provider: event.target.value })}><option value="">Choose simulation provider</option>{managedProviders.filter((provider) => provider.verification_status === 'simulated').map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}</select></label>
              <label>Vehicle identifier<input required value={draft.vehicle_identifier} onChange={(event) => setDraft({ ...draft, vehicle_identifier: event.target.value })} /></label>
              <label>Capabilities<input value={draft.vehicle_capabilities} onChange={(event) => setDraft({ ...draft, vehicle_capabilities: event.target.value })} placeholder="basic_life_support, oxygen" /></label>
              <p className="directory-note">Created as simulated and unavailable, and only under a simulation-only provider. This form cannot create or authorize a live provider feed.</p><button disabled={busy || !managedProviders.some((provider) => provider.id === draft.vehicle_provider && provider.verification_status === 'simulated')}>Create simulated vehicle</button></form></details>
          </div>
          <div className="directory-admin-lists">
            <section><h3>All providers · {managedProviders.length}</h3>{managedProviders.map((provider) => <article key={provider.id}><div><strong>{provider.name}</strong><small>{provider.dispatch_phone_number || 'No dispatch number'} · {provider.verification_status}</small><small>{provider.verification_source || 'Verification source not recorded'}</small></div><StatusBadge value={provider.verification_status} />{provider.verification_status !== 'verified' && <div className="directory-verify"><input aria-label={`Verification source for ${provider.name}`} placeholder="Verification source/reference" value={verificationSources[`provider:${provider.id}`] || ''} onChange={(event) => setVerificationSources({ ...verificationSources, [`provider:${provider.id}`]: event.target.value })} /><button type="button" disabled={busy} onClick={() => verifyRecord('provider', provider.id)}><CheckCircle2 size={14} /> Verify</button></div>}</article>)}</section>
            <section><h3>All facilities · {managedFacilities.length}</h3>{managedFacilities.map((facility) => <article key={facility.id}><div><strong>{facility.name}</strong><small>{facility.address || 'Address not recorded'} · {facility.latitude}, {facility.longitude}</small><small>{facility.verification_source || 'Verification source not recorded'}</small></div><StatusBadge value={facility.verification_status} />{facility.verification_status !== 'verified' && <div className="directory-verify"><input aria-label={`Verification source for ${facility.name}`} placeholder="Verification source/reference" value={verificationSources[`facility:${facility.id}`] || ''} onChange={(event) => setVerificationSources({ ...verificationSources, [`facility:${facility.id}`]: event.target.value })} /><button type="button" disabled={busy} onClick={() => verifyRecord('facility', facility.id)}><CheckCircle2 size={14} /> Verify</button></div>}</article>)}</section>
            <section><h3>All vehicles · {managedVehicles.length}</h3>{managedVehicles.map((vehicle) => <article key={vehicle.id}><div><strong>{vehicle.vehicle_identifier}</strong><small>{vehicle.provider_name} · {vehicle.data_source} · {vehicle.availability}</small></div><StatusBadge value={vehicle.data_source === 'simulator' ? 'simulated' : vehicle.availability} /></article>)}</section>
          </div>
        </section>}
      </>}
    </div>
  )
}