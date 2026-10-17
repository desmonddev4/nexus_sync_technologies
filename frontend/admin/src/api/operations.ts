import { apiRequest } from './client'
import type {
  CurrentUser,
  EmergencyProvider,
  HealthcareFacility,
  Incident,
  IncidentEvent,
  IncidentNotification,
  NearbyVehicle,
  Patient,
} from '../types/api'

export function getCurrentUser() { return apiRequest<CurrentUser>('auth/me/') }
export function getIncidents() { return apiRequest<Incident[]>('incidents/') }
export function getIncident(id: string) { return apiRequest<Incident>(`incidents/${id}/`) }
export function getPatient(id: string) { return apiRequest<Patient>(`patients/${id}/`) }
export function getIncidentEvents(id: string) { return apiRequest<IncidentEvent[]>(`incidents/${id}/events/`) }
export function getIncidentNotifications(id: string) { return apiRequest<IncidentNotification[]>(`incidents/${id}/notifications/`) }
export function acknowledgeIncident(id: string) { return apiRequest<Incident>(`incidents/${id}/acknowledge/`, { method: 'POST' }) }

export function getNearbyVehicles(latitude: string, longitude: string, includeSimulated: boolean) {
  const query = new URLSearchParams({ latitude, longitude })
  if (includeSimulated) query.set('include_simulated', 'true')
  return apiRequest<NearbyVehicle[]>(`vehicles/nearby/?${query.toString()}`)
}

export function assignResponder(id: string, vehicle: string, includeSimulated: boolean) {
  return apiRequest<Incident>(`incidents/${id}/assign-responder/`, {
    method: 'POST', body: JSON.stringify({ vehicle, include_simulated: includeSimulated }),
  })
}

export function requestDispatch(id: string) {
  return apiRequest<{ incident: Incident; provider_contacted_by_system: false; note: string }>(
    `incidents/${id}/record-dispatch-request/`, { method: 'POST' },
  )
}

export function confirmDispatch(id: string, confirmationReference: string) {
  return apiRequest<{ incident: Incident; confirmation_source: string; note: string }>(
    `incidents/${id}/record-dispatch-confirmation/`, {
      method: 'POST', body: JSON.stringify({ confirmation_reference: confirmationReference }),
    },
  )
}

export function advanceIncident(id: string, status: string) {
  return apiRequest<Incident>(`incidents/${id}/status/`, {
    method: 'POST', body: JSON.stringify({ status }),
  })
}

export function calculateRoute(id: string) {
  return apiRequest<{
    id: string
    distance_meters: number
    duration_seconds: number
    duration_minutes: number
    encoded_polyline: string
    is_simulated: boolean
    computed_at: string
  }>(`incidents/${id}/route/`, { method: 'POST' })
}

export function getPatients() { return apiRequest<Patient[]>('patients/') }
export function getProviders() { return apiRequest<EmergencyProvider[]>('providers/') }
export function getFacilities() { return apiRequest<HealthcareFacility[]>('facilities/') }
export function getVehicles() { return apiRequest<NearbyVehicle[]>('vehicles/') }