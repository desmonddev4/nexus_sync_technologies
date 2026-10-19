import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactNode } from 'react'
import { OperationsMapPage } from './OperationsMapPage'
import type { Incident } from '../../types/api'

const { getIncidents, getFacilities, getProviders, getNearbyVehicles, calculateRoute } = vi.hoisted(() => ({
  getIncidents: vi.fn(),
  getFacilities: vi.fn(),
  getProviders: vi.fn(),
  getNearbyVehicles: vi.fn(),
  calculateRoute: vi.fn(),
}))

vi.mock('../../api/operations', () => ({ getIncidents, getFacilities, getProviders, getNearbyVehicles, calculateRoute }))
vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: ReactNode }) => <div aria-label="map">{children}</div>,
  Marker: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  ZoomControl: () => null,
  TileLayer: () => null,
  Polyline: () => <div data-testid="route-polyline" />,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  useMap: () => ({ setView: vi.fn(), fitBounds: vi.fn(), flyToBounds: vi.fn() }),
}))

const incident: Incident = {
  id: '11111111-1111-1111-1111-111111111111',
  patient: 'patient-1',
  source_event_id: 'event-1',
  incident_type: 'manual_sos',
  priority: 'high',
  trigger_source: 'manual_sos',
  status: 'created',
  location: { latitude: '5.6508', longitude: '-0.1869', accuracy_meters: '12', source: 'simulator', quality: 'valid', recorded_at: new Date().toISOString(), received_at: new Date().toISOString(), age_seconds: 20, is_stale: false },
  assigned_vehicle: null,
  assigned_vehicle_identifier: null,
  assigned_provider_name: null,
  assigned_vehicle_source: null,
  assigned_operator: null,
  is_simulated_dispatch: false,
  dispatch_requested_at: null,
  dispatch_confirmed_at: null,
  dispatch_confirmation_reference: '',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
}

describe('OperationsMapPage', () => {
  beforeEach(() => {
    getIncidents.mockReset().mockResolvedValue([incident])
    getFacilities.mockReset().mockResolvedValue([{ id: 'facility-1', name: 'Pilot Clinic', facility_type: 'clinic', address: 'Madina', phone_number: '', latitude: '5.66', longitude: '-0.19', verification_status: 'verified' }])
    getProviders.mockReset().mockResolvedValue([{ id: 'provider-1', name: 'Verified Provider', provider_type: 'private_ambulance', address: 'East Legon', latitude: '5.67', longitude: '-0.18', coverage_description: 'Accra', verification_status: 'verified' }])
    getNearbyVehicles.mockReset().mockResolvedValue([{ id: 'vehicle-1', provider: 'provider-1', provider_name: 'Verified Provider', provider_verification_status: 'verified', vehicle_identifier: 'SIM-01', capabilities: [], availability: 'available', data_source: 'simulator', is_simulated: true, latitude: '5.64', longitude: '-0.2', location_accuracy_meters: 10, location_updated_at: new Date().toISOString(), current_incident: null, distance_kilometers: 1.1 }])
    calculateRoute.mockReset()
  })

  it('shows incident, verified directory markers, and explicitly labeled simulator vehicle', async () => {
    render(<MemoryRouter><OperationsMapPage /></MemoryRouter>)

    expect(await screen.findByText(/SIMULATED POSITION/)).toBeInTheDocument()
    expect(screen.getByText('Pilot Clinic')).toBeInTheDocument()
    expect(screen.getByText('Verified Provider')).toBeInTheDocument()
    expect(screen.getByText(/not dispatch confirmation/i)).toBeInTheDocument()
    expect(screen.getByText('located')).toBeInTheDocument()
  })

  it('does not request vehicles for a stale incident location', async () => {
    getIncidents.mockResolvedValue([{ ...incident, location: { ...incident.location!, is_stale: true } }])
    render(<MemoryRouter><OperationsMapPage /></MemoryRouter>)

    await waitFor(() => expect(screen.getByText(/STALE · 5.6508/)).toBeInTheDocument())
    expect(getNearbyVehicles).not.toHaveBeenCalled()
  })

  it('shows missing incident location without inventing coordinates or requesting vehicles', async () => {
    getIncidents.mockResolvedValue([{ ...incident, location: null }])
    render(<MemoryRouter><OperationsMapPage /></MemoryRouter>)

    expect(await screen.findByText('No location snapshot', { selector: 'small' })).toBeInTheDocument()
    expect(screen.getByText('no location').previousElementSibling).toHaveTextContent('1')
    expect(getNearbyVehicles).not.toHaveBeenCalled()
  })

  it('renders calculated route geometry as an ETA estimate, not dispatch confirmation', async () => {
    getIncidents.mockResolvedValue([{
      ...incident,
      assigned_vehicle: 'vehicle-1',
      assigned_vehicle_identifier: 'SIM-01',
      assigned_provider_name: 'Simulated Provider',
      assigned_vehicle_source: 'simulator',
      is_simulated_dispatch: true,
    }])
    calculateRoute.mockResolvedValue({
      id: 'route-1',
      distance_meters: 1250,
      duration_seconds: 420,
      duration_minutes: 7,
      encoded_polyline: '_p~iF~ps|U_ulLnnqC_mqNvxq`@',
      is_simulated: true,
      computed_at: new Date().toISOString(),
    })
    render(<MemoryRouter><OperationsMapPage /></MemoryRouter>)

    const routeButton = await screen.findByRole('button', { name: 'Show assigned route and ETA' })
    fireEvent.click(routeButton)

    expect((await screen.findAllByTestId('route-polyline'))).toHaveLength(2)
    expect(await screen.findByText(/1\.3 km · 7 min · simulated route · estimate only, not dispatch confirmation/)).toBeInTheDocument()
  })

  it('warns when a returned nearby vehicle position has since gone stale', async () => {
    getNearbyVehicles.mockResolvedValue([{
      id: 'vehicle-stale',
      provider: 'provider-1',
      provider_name: 'Verified Provider',
      provider_verification_status: 'verified',
      vehicle_identifier: 'STALE-01',
      capabilities: [],
      availability: 'available',
      data_source: 'provider',
      is_simulated: false,
      latitude: '5.64',
      longitude: '-0.2',
      location_accuracy_meters: null,
      location_updated_at: new Date(Date.now() - 10 * 60_000).toISOString(),
      current_incident: null,
      distance_kilometers: 1.1,
    }])
    render(<MemoryRouter><OperationsMapPage /></MemoryRouter>)

    await waitFor(() => expect(getNearbyVehicles).toHaveBeenCalled())
    expect(await screen.findByText(/STALE — refresh before relying on this position/)).toBeInTheDocument()
  })
})
