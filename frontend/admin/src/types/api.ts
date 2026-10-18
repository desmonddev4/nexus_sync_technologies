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
  emergency_contacts?: EmergencyContact[]
  consent_records?: ConsentRecord[]
  created_at: string
  updated_at: string
}

export interface EmergencyContact {
  id: string
  name: string
  relationship: string
  phone_number: string
  notification_preferences: Record<string, unknown>
  priority_order: number
  verification_status: string
  created_at: string
  updated_at: string
}

export interface ConsentRecord {
  id: string
  scope: string
  status: string
  policy_version: string
  recorded_at: string
  created_at: string
  updated_at: string
}

export interface Measurement {
  id: string
  patient: string
  device: string | null
  event_id: string
  measurement_type: string
  value: string
  unit: string
  source: string
  quality: string
  measured_at: string
  received_at: string
}

export interface PatientLocation {
  id: string
  patient: string
  device: string | null
  event_id: string
  latitude: string
  longitude: string
  accuracy_meters: string | null
  source: string
  quality: string
  recorded_at: string
  received_at: string
}

export interface DeviceHealth {
  id: string
  device_identifier: string
  device_type: string
  status: string
  firmware_version: string
  battery_percent: number | null
  last_seen_at: string | null
  last_seen_age_seconds: number | null
  is_stale: boolean
  credential_revoked: boolean | null
  created_at: string
  updated_at: string
}

export interface MonitoringRule {
  id: string
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
  is_enabled: boolean
  reviewed_by: number | null
  reviewed_by_username: string | null
  reviewed_at: string | null
  evaluation_count: number
  created_at: string
  updated_at: string
}

export interface MonitoringRuleEvaluation {
  id: string
  rule: string
  measurement: string
  incident: string | null
  status: string
  details: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface AuditLogEntry {
  id: string
  created_at: string
  actor: number | null
  actor_username: string | null
  action: string
  resource_type: string
  resource_id: string
  outcome: 'success' | 'denied' | 'failure'
  http_method: string
  ip_address: string | null
  request_id: string
  metadata: Record<string, unknown>
}

export interface AccountAdmin {
  id: number
  username: string
  email: string
  is_active: boolean
  date_joined: string
  last_login: string | null
  role: string | null
  phone_number: string
  patient: string | null
}

export interface EscalationPolicy {
  id: string
  initial_notification_timeout_minutes: number
  retry_interval_minutes: number
  max_retry_attempts: number
  escalate_to_coordinator_after_minutes: number
  require_operator_acknowledgement: boolean
  allow_simulation_escalation: boolean
  notes: string
  updated_by: number | null
  updated_by_username: string | null
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
  latitude?: string | null
  longitude?: string | null
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

export interface MeasurementQualityReview extends Measurement {
  patient_name: string
  quality_reviewed_by: number | null
  quality_reviewed_at: string | null
}