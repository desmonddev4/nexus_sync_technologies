import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { IncidentsPage } from './IncidentsPage'
import type { Incident } from '../../types/api'

vi.mock('../../api/operations', () => ({
  getIncidents: vi.fn(),
}))

import { getIncidents } from '../../api/operations'

const mockGetIncidents = vi.mocked(getIncidents)

const now = new Date().toISOString()

const baseIncident: Incident = {
  id: '11111111-1111-1111-1111-111111111111',
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
    age_seconds: 45,
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

describe('IncidentsPage', () => {
  beforeEach(() => {
    mockGetIncidents.mockReset()
  })

  it('renders stale location and simulated dispatch labels', async () => {
    mockGetIncidents.mockResolvedValue([
      {
        ...baseIncident,
        id: '22222222-2222-2222-2222-222222222222',
        location: {
          ...baseIncident.location!,
          is_stale: true,
        },
        is_simulated_dispatch: true,
        assigned_vehicle_identifier: 'AMB-07',
      },
    ])

    render(
      <MemoryRouter>
        <IncidentsPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.queryByText('Loading incident records…')).not.toBeInTheDocument()
    })

    expect(screen.getByText('STALE LOCATION')).toBeInTheDocument()
    expect(screen.getByText('SIMULATED ONLY')).toBeInTheDocument()
  })

  it('filters out closed incidents in active mode and shows them in closed mode', async () => {
    mockGetIncidents.mockResolvedValue([
      {
        ...baseIncident,
        id: '33333333-3333-3333-3333-333333333333',
        incident_type: 'fall_detected',
        status: 'created',
      },
      {
        ...baseIncident,
        id: '44444444-4444-4444-4444-444444444444',
        incident_type: 'rule_alert',
        status: 'closed',
      },
    ])

    render(
      <MemoryRouter>
        <IncidentsPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.queryByText('Loading incident records…')).not.toBeInTheDocument()
    })

    const table = screen.getByRole('table')
    expect(within(table).queryByText('rule alert')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Closed' }))

    expect(within(table).getByText('rule alert')).toBeInTheDocument()
    expect(within(table).queryByText('fall detected')).not.toBeInTheDocument()
  })
})
