import { apiRequest } from './client'
import type {
  AccountAdmin,
  AuditLogEntry,
  CurrentUser,
  DeviceHealth,
  DeviceRegistryRecord,
  EmergencyProvider,
  FacilityDirectoryRecord,
  EscalationPolicy,
  HealthcareFacility,
  Incident,
  IncidentEvent,
  IncidentNotification,
  IssuedDeviceCredential,
  Measurement,
  MeasurementQualityReview,
  MonitoringRule,
  MonitoringRuleEvaluation,
  NearbyVehicle,
  Patient,
  PatientLocation,
  ProviderDirectoryRecord,
  VehicleDirectoryRecord,
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
export function createPatient(payload: Pick<Patient, 'full_name' | 'phone_number' | 'status'> & { date_of_birth?: string | null; relevant_medical_notes?: string }) {
  return apiRequest<Patient>('patients/', { method: 'POST', body: JSON.stringify(payload) })
}
export function getPatientMeasurements(id: string, limit = 20) {
  return apiRequest<Measurement[]>(`patients/${id}/measurements/?limit=${limit}`)
}
export function getPatientLocations(id: string, limit = 20) {
  return apiRequest<PatientLocation[]>(`patients/${id}/locations/?limit=${limit}`)
}
export function getPatientDevices(id: string) {
  return apiRequest<DeviceHealth[]>(`patients/${id}/devices/`)
}
export function getDeviceRegistry() { return apiRequest<DeviceRegistryRecord[]>('device-registry/') }
export function createRegistryDevice(payload: { device_identifier: string; device_type: string; patient: string | null; status: string }) {
  return apiRequest<DeviceRegistryRecord>('device-registry/', { method: 'POST', body: JSON.stringify(payload) })
}
export function updateRegistryDevice(id: string, payload: { patient?: string | null; status?: string }) {
  return apiRequest<DeviceRegistryRecord>(`device-registry/${id}/`, { method: 'PATCH', body: JSON.stringify(payload) })
}
export function issueDeviceCredential(id: string) {
  return apiRequest<IssuedDeviceCredential>(`device-registry/${id}/issue-credential/`, { method: 'POST' })
}
export function revokeDeviceCredential(id: string) {
  return apiRequest<DeviceRegistryRecord>(`device-registry/${id}/revoke-credential/`, { method: 'POST' })
}

export function getManagedProviders() { return apiRequest<ProviderDirectoryRecord[]>('directory/providers/') }
export function createManagedProvider(payload: Partial<ProviderDirectoryRecord> & { name: string; provider_type: string }) {
  return apiRequest<ProviderDirectoryRecord>('directory/providers/', { method: 'POST', body: JSON.stringify(payload) })
}
export function verifyManagedProvider(id: string, verification_source: string) {
  return apiRequest<ProviderDirectoryRecord>(`directory/providers/${id}/verify/`, { method: 'POST', body: JSON.stringify({ verification_source }) })
}
export function getManagedFacilities() { return apiRequest<FacilityDirectoryRecord[]>('directory/facilities/') }
export function createManagedFacility(payload: Partial<FacilityDirectoryRecord> & { name: string; facility_type: string; latitude: string; longitude: string }) {
  return apiRequest<FacilityDirectoryRecord>('directory/facilities/', { method: 'POST', body: JSON.stringify(payload) })
}
export function verifyManagedFacility(id: string, verification_source: string) {
  return apiRequest<FacilityDirectoryRecord>(`directory/facilities/${id}/verify/`, { method: 'POST', body: JSON.stringify({ verification_source }) })
}
export function getManagedVehicles() { return apiRequest<VehicleDirectoryRecord[]>('directory/vehicles/') }
export function createManagedVehicle(payload: { provider: string; vehicle_identifier: string; capabilities: string[]; data_source: string; availability: string }) {
  return apiRequest<VehicleDirectoryRecord>('directory/vehicles/', { method: 'POST', body: JSON.stringify(payload) })
}
export function getMonitoringRules() {
  return apiRequest<MonitoringRule[]>('monitoring/rules/')
}
export function getMeasurementQualityQueue(limit = 50) {
  return apiRequest<MeasurementQualityReview[]>(`measurements/review/?limit=${limit}`)
}
export function reviewMeasurementQuality(measurementId: string, quality: 'acceptable' | 'questionable') {
  return apiRequest<MeasurementQualityReview>(`measurements/${measurementId}/review/`, {
    method: 'POST',
    body: JSON.stringify({ quality }),
  })
}
export function createMonitoringRule(payload: {
  name: string
  description: string
  measurement_type: string
  operator: 'gt' | 'gte' | 'lt' | 'lte'
  threshold: string
  priority: 'low' | 'medium' | 'high' | 'critical'
  minimum_consecutive_readings: number
  lookback_window_seconds: number
  include_simulated: boolean
  version: string
}) {
  return apiRequest<MonitoringRule>('monitoring/rules/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function reviewMonitoringRule(ruleId: string, isEnabled: boolean) {
  return apiRequest<MonitoringRule>(`monitoring/rules/${ruleId}/review/`, {
    method: 'POST',
    body: JSON.stringify({ is_enabled: isEnabled }),
  })
}
export function getMonitoringRuleEvaluations(ruleId: string, limit = 20) {
  return apiRequest<MonitoringRuleEvaluation[]>(`monitoring/rules/${ruleId}/evaluations/?limit=${limit}`)
}
export function getAuditLogs(filters: {
  actor?: string
  action?: string
  resource?: string
  outcome?: 'success' | 'denied' | 'failure' | ''
  start_date?: string
  end_date?: string
  limit?: number
} = {}) {
  const query = new URLSearchParams()
  if (filters.actor) query.set('actor', filters.actor)
  if (filters.action) query.set('action', filters.action)
  if (filters.resource) query.set('resource', filters.resource)
  if (filters.outcome) query.set('outcome', filters.outcome)
  if (filters.start_date) query.set('start_date', filters.start_date)
  if (filters.end_date) query.set('end_date', filters.end_date)
  query.set('limit', String(filters.limit || 100))
  return apiRequest<AuditLogEntry[]>(`audit/logs/?${query.toString()}`)
}
export function getAccounts(search = '', role = '') {
  const query = new URLSearchParams()
  if (search) query.set('search', search)
  if (role) query.set('role', role)
  const queryString = query.toString()
  return apiRequest<AccountAdmin[]>(`accounts/${queryString ? `?${queryString}` : ''}`)
}
export function createAccount(payload: {
  username: string
  email: string
  password: string
  is_active: boolean
  role: string
  phone_number: string
  patient: string | null
}) {
  return apiRequest<AccountAdmin>('accounts/', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
export function updateAccount(accountId: number, payload: {
  email?: string
  password?: string
  is_active?: boolean
  role?: string
  phone_number?: string
  patient?: string | null
}) {
  return apiRequest<AccountAdmin>(`accounts/${accountId}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
export function getEscalationPolicy() {
  return apiRequest<EscalationPolicy>('settings/escalation-policy/')
}
export function updateEscalationPolicy(payload: Partial<Pick<
  EscalationPolicy,
  | 'initial_notification_timeout_minutes'
  | 'retry_interval_minutes'
  | 'max_retry_attempts'
  | 'escalate_to_coordinator_after_minutes'
  | 'require_operator_acknowledgement'
  | 'allow_simulation_escalation'
  | 'notes'
>>) {
  return apiRequest<EscalationPolicy>('settings/escalation-policy/', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}
export function getProviders() { return apiRequest<EmergencyProvider[]>('providers/') }
export function getFacilities() { return apiRequest<HealthcareFacility[]>('facilities/') }
export function getVehicles() { return apiRequest<NearbyVehicle[]>('vehicles/') }