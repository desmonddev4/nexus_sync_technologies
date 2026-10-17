export type IncidentStatus =
  | 'created'
  | 'acknowledged'
  | 'responder_assigned'
  | 'dispatch_requested'
  | 'dispatch_confirmed'
  | 'responder_en_route'
  | 'arrived'
  | 'resolved'
  | 'closed'
  | 'declined'
  | 'cancelled'

export interface CurrentUser {
  username: string
  role: string | null
  can_access_operations: boolean
}

export interface IncidentLocation {
  latitude: string
  longitude: string
  accuracy_meters: string | null
  source: string
  quality: string
  recorded_at: string
  received_at: string
  age_seconds: number
  is_stale: boolean
}

export interface Incident {
  id: string
  patient: string
  source_event_id: string
  incident_type: string
  priority: string
  trigger_source: string
  status: IncidentStatus
  location: IncidentLocation | null
  assigned_vehicle: string | null
  assigned_vehicle_identifier: string | null
  assigned_provider_name: string | null
  assigned_vehicle_source: string | null
  assigned_operator: number | null
  is_simulated_dispatch: boolean
  dispatch_requested_at: string | null
  dispatch_confirmed_at: string | null
  dispatch_confirmation_reference: string
  created_at: string
  updated_at: string
}

export interface Patient {
  id: string
  full_name: string
  date_of_birth: string | null
  phone_number: string
  relevant_medical_notes: string
  status: 'active' | 'inactive'
  created_at: string
  updated_at: string
}

export interface IncidentEvent {
  id: string
  event_type: string
  actor: number | null
  details: Record<string, unknown>
  created_at: string
}

export interface IncidentNotification {
  id: string
  contact_name: string | null
  channel: string
  status: string
  retry_count: number
  last_attempt_at: string | null
  submitted_at: string | null
  delivered_at: string | null
  acknowledged_at: string | null
  provider_name: string
  provider_task_id: string
  provider_status_updated_at: string | null
  failure_code: string
  created_at: string
}

export interface EmergencyProvider {
  id: string
  name: string
  provider_type: string
  dispatch_phone_number: string
  general_phone_number: string
  address: string
  coverage_description: string
  verification_status: string
  verified_at: string | null
}

export interface HealthcareFacility {
  id: string
  name: string
  facility_type: string
  address: string
  phone_number: string
  latitude: string
  longitude: string
  verification_status: string
}

export interface NearbyVehicle {
  id: string
  provider: string
  provider_name: string
  provider_verification_status: string
  vehicle_identifier: string
  capabilities: string[]
  availability: string
  data_source: string
  is_simulated: boolean
  latitude: string
  longitude: string
  location_accuracy_meters: number | null
  location_updated_at: string | null
  current_incident: string | null
  distance_kilometers: number
}