import { useEffect, useState } from 'react'
import { Ambulance, Building2, RadioTower } from 'lucide-react'
import { getFacilities, getProviders, getVehicles } from '../../api/operations'
import type { EmergencyProvider, HealthcareFacility, NearbyVehicle } from '../../types/api'
import { EmptyState } from '../../components/EmptyState/EmptyState'
import { StatusBadge } from '../../components/StatusBadge/StatusBadge'
import './ServicesPage.css'

export function ServicesPage() {
  const [providers, setProviders] = useState<EmergencyProvider[]>([])
  const [facilities, setFacilities] = useState<HealthcareFacility[]>([])
  const [vehicles, setVehicles] = useState<NearbyVehicle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([getProviders(), getFacilities(), getVehicles()])
      .then(([providerData, facilityData, vehicleData]) => { setProviders(providerData); setFacilities(facilityData); setVehicles(vehicleData) })
      .catch((reason: Error) => setError(reason.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="services-page">
      <header className="page-heading"><div><p className="page-eyebrow">OPERATIONS / DIRECTORY</p><h1>Emergency services</h1><p className="page-subtitle">Only verified providers and facilities appear in operational lists.</p></div></header>
      {error && <div className="page-error" role="alert">Unable to load directory: {error}</div>}
      {loading ? <div className="loading-row">Loading verified directory…</div> : <div className="service-columns">
        <section className="service-section"><div className="service-section-heading"><RadioTower size={17} /><div><p className="page-eyebrow">RESPONSE NETWORK</p><h2>Providers <span>{providers.length}</span></h2></div></div>
          {providers.length === 0 ? <EmptyState icon={RadioTower} title="No verified providers" detail="Provider contact and verification must be completed first." /> : providers.map((provider) => <article className="service-row" key={provider.id}><div><strong>{provider.name}</strong><small>{provider.provider_type.replaceAll('_', ' ')}</small><small>{provider.dispatch_phone_number ? `Dispatch ${provider.dispatch_phone_number}` : 'No dispatch number recorded'}</small><small>{provider.coverage_description || 'Coverage not recorded'}</small></div><StatusBadge value={provider.verification_status} /></article>)}
        </section>
        <section className="service-section"><div className="service-section-heading"><Building2 size={17} /><div><p className="page-eyebrow">RECEIVING FACILITIES</p><h2>Facilities <span>{facilities.length}</span></h2></div></div>
          {facilities.length === 0 ? <EmptyState icon={Building2} title="No verified facilities" detail="Only facilities with verified information are listed." /> : facilities.map((facility) => <article className="service-row" key={facility.id}><div><strong>{facility.name}</strong><small>{facility.facility_type} · {facility.address || 'Address not recorded'}</small><small>{facility.phone_number || 'No phone recorded'}</small><small>{facility.latitude}, {facility.longitude}</small></div><StatusBadge value={facility.verification_status} /></article>)}
        </section>
        <section className="service-section"><div className="service-section-heading"><Ambulance size={17} /><div><p className="page-eyebrow">FLEET STATUS</p><h2>Vehicles <span>{vehicles.length}</span></h2></div></div>
          {vehicles.length === 0 ? <EmptyState icon={Ambulance} title="No vehicle feed" detail="Live vehicle locations require an authorized provider feed." /> : vehicles.map((vehicle) => <article className="service-row" key={vehicle.id}><div><strong>{vehicle.vehicle_identifier}</strong><small>{vehicle.provider_name} · {vehicle.capabilities.join(', ') || 'Capability not recorded'}</small><small>{vehicle.location_updated_at ? `Updated ${new Date(vehicle.location_updated_at).toLocaleString()}` : 'Location time unknown'}</small>{vehicle.is_simulated && <small className="simulated-copy">Simulation only — not a real ambulance.</small>}</div><StatusBadge value={vehicle.is_simulated ? 'simulated' : vehicle.availability} /></article>)}
        </section>
      </div>}
    </div>
  )
}