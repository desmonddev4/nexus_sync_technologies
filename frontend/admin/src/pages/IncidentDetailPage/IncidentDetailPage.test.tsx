import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { IncidentDetailPage } from './IncidentDetailPage'
import type { Incident, IncidentEvent, IncidentNotification } from '../../types/api'

vi.mock('../../api/operations', () => ({
  acknowledgeIncident: vi.fn(),
  advanceIncident: vi.fn(),
  assignResponder: vi.fn(),
  calculateRoute: vi.fn(),
  confirmDispatch: vi.fn(),
  getIncident: vi.fn(),
  getIncidentEvents: vi.fn(),
  getIncidentNotifications: vi.fn(),
  getNearbyVehicles: vi.fn(),
  requestDispatch: vi.fn(),
}))

import {
  acknowledgeIncident,
  confirmDispatch,
  getIncident,
  getIncidentEvents,
  getIncidentNotifications,
} from '../../api/operations'

const mockGetIncident = vi.mocked(getIncident)
const mockGetIncidentEvents = vi.mocked(getIncidentEvents)
const mockGetIncidentNotifications = vi.mocked(getIncidentNotifications)
const mockAcknowledgeIncident = vi.mocked(acknowledgeIncident)
const mockConfirmDispatch = vi.mocked(confirmDispatch)

const now = new Date().toISOString()

const baseIncident: Incident = {
  id: '88888888-1111-2222-3333-444444444444',
  patient: 'patient-1',
  source_event_id: 'event-1',
  incident_type: 'manual_sos',
  priority: 'high',
  trigger_source: 'manual_sos',
  status: 'created',
  location: {
    latitude: '5.6037',
    longitude: '-0.1870',
    accuracy_meters: '12.0',
    source: 'gps',
    quality: 'accepted',
    recorded_at: now,
    received_at: now,
    age_seconds: 30,
    is_stale: false,
  },
  assigned_vehicle: null,
  assigned_vehicle_identifier: null,
  assigned_provider_name: null,
  assigned_vehicle_source: null,
  assigned_operator: null,
  is_simulated_dispatch: false,
  dispatch_requested_at: null,
  dispatch_confirmed_at: null,
  dispatch_confirmation_reference: '',
  created_at: now,
  updated_at: now,
}

const events: IncidentEvent[] = []
const notifications: IncidentNotification[] = []

function renderDetailPage() {
  return render(
    <MemoryRouter initialEntries={[`/incidents/${baseIncident.id}`]}>
      <Routes>
        <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('IncidentDetailPage workflows', () => {
  beforeEach(() => {
    mockGetIncident.mockReset()
    mockGetIncidentEvents.mockReset()
    mockGetIncidentNotifications.mockReset()
    mockAcknowledgeIncident.mockReset()
    mockConfirmDispatch.mockReset()

    mockGetIncidentEvents.mockResolvedValue(events)
    mockGetIncidentNotifications.mockResolvedValue(notifications)
    mockAcknowledgeIncident.mockResolvedValue(baseIncident)
    mockConfirmDispatch.mockResolvedValue({
      incident: baseIncident,
      confirmation_source: 'operator_recorded',
      note: 'ok',
    })
  })

  it('acknowledges a created incident', async () => {
    mockGetIncident
      .mockResolvedValueOnce(baseIncident)
      .mockResolvedValueOnce({ ...baseIncident, status: 'acknowledged' })

    renderDetailPage()

    const acknowledgeButton = await screen.findByRole('button', { name: 'Acknowledge' })
    fireEvent.click(acknowledgeButton)

    await waitFor(() => {
      expect(mockAcknowledgeIncident).toHaveBeenCalledWith(baseIncident.id)
    })

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument()
    })
  })

  it('records dispatch confirmation reference for dispatch requested incident', async () => {
    const dispatchRequested = {
      ...baseIncident,
      status: 'dispatch_requested' as const,
    }

    mockGetIncident
      .mockResolvedValueOnce(dispatchRequested)
      .mockResolvedValueOnce({
        ...dispatchRequested,
        status: 'dispatch_confirmed',
        dispatch_confirmation_reference: 'CALL-123',
        dispatch_confirmed_at: now,
      })

    renderDetailPage()

    const input = await screen.findByLabelText('Provider confirmation reference')
    fireEvent.change(input, { target: { value: 'CALL-123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record confirmation' }))

    await waitFor(() => {
      expect(mockConfirmDispatch).toHaveBeenCalledWith(baseIncident.id, 'CALL-123')
    })

    await waitFor(() => {
      expect(screen.getByText(/Operator-reported confirmation:/i)).toBeInTheDocument()
    })
  })
})
