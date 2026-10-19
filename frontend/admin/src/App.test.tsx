import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import type { CurrentUser } from './types/api'

const mockApiRequest = vi.fn()

vi.mock('./api/client', () => ({
  apiRequest: (...args: unknown[]) => mockApiRequest(...args),
  getAuthToken: vi.fn(() => null),
  saveAuthToken: vi.fn(),
  clearAuthToken: vi.fn(),
}))

import App from './App'
import { getAuthToken } from './api/client'
import * as operations from './api/operations'

vi.mock('./api/operations', () => ({
  getPatients: vi.fn(),
  getPatient: vi.fn(),
  getPatientMeasurements: vi.fn(),
  getPatientLocations: vi.fn(),
  getPatientDevices: vi.fn(),
  getDeviceRegistry: vi.fn(),
}))

function renderApp(pathname: string) {
  window.history.pushState({}, 'test', pathname)
  return render(<App />)
}

describe('App auth access control', () => {
  beforeEach(() => {
    mockApiRequest.mockReset()
    vi.mocked(getAuthToken).mockReturnValue(null)
  })

  it('shows login page when unauthenticated on protected route', async () => {
    renderApp('/incidents')

    expect(await screen.findByRole('heading', { name: 'Sign in to operations' })).toBeInTheDocument()
  })

  it('allows authorized operations user into the dashboard', async () => {
    const user: CurrentUser = {
      username: 'coordinator1',
      role: 'emergency_coordinator',
      can_access_operations: true,
    }

    vi.mocked(getAuthToken).mockReturnValue('token-1')
    mockApiRequest
      .mockResolvedValueOnce(user)
      .mockResolvedValueOnce([])

    renderApp('/')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Operations overview' })).toBeInTheDocument()
    })
  })

  it('submits login form and navigates to dashboard', async () => {
    const user: CurrentUser = {
      username: 'coordinator1',
      role: 'emergency_coordinator',
      can_access_operations: true,
    }

    mockApiRequest
      .mockResolvedValueOnce({ token: 'token-2' })
      .mockResolvedValueOnce(user)
      .mockResolvedValueOnce([])

    renderApp('/login')

    fireEvent.change(screen.getByLabelText('Username'), { target: { value: '  coordinator1  ' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'secret-pass' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => {
      expect(mockApiRequest).toHaveBeenCalledWith('auth/token/', {
        method: 'POST',
        body: JSON.stringify({ username: 'coordinator1', password: 'secret-pass' }),
      })
    })

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Operations overview' })).toBeInTheDocument()
    })
  })

  it('returns unauthorized operations user to login', async () => {
    const user: CurrentUser = {
      username: 'viewer',
      role: 'patient',
      can_access_operations: false,
    }

    vi.mocked(getAuthToken).mockReturnValue('token-1')
    mockApiRequest.mockResolvedValue(user)

    renderApp('/')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Sign in to operations' })).toBeInTheDocument()
    })
  })

  it('renders the wearable demo page for authorized operators', async () => {
    const user: CurrentUser = {
      username: 'coordinator1',
      role: 'emergency_coordinator',
      can_access_operations: true,
    }

    vi.mocked(getAuthToken).mockReturnValue('token-1')
    mockApiRequest.mockResolvedValueOnce(user).mockResolvedValueOnce([])

    renderApp('/demo')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'Wearable demo' })).toBeInTheDocument()
    })
  })

  it('opens a real device overview page from the registry for authorized operators', async () => {
    const user: CurrentUser = {
      username: 'coordinator1',
      role: 'emergency_coordinator',
      can_access_operations: true,
    }

    vi.mocked(getAuthToken).mockReturnValue('token-1')
    mockApiRequest.mockResolvedValueOnce(user).mockResolvedValueOnce([])
    vi.mocked(operations.getDeviceRegistry).mockResolvedValue([
      {
        id: 'dev-1',
        device_identifier: 'NS-SIM-001',
        patient: 'pat-123',
        device_type: 'simulator',
        status: 'active',
        firmware_version: '1.0.0',
        battery_percent: 68,
        last_seen_at: '2025-01-01T00:00:00Z',
        credential_revoked: false,
        credential_last_used_at: null,
        created_at: '2025-01-01T00:00:00Z',
        updated_at: '2025-01-01T00:00:00Z',
      },
    ])
    vi.mocked(operations.getPatients).mockResolvedValue([
      { id: 'pat-123', full_name: 'Ada Mensah', status: 'active', phone_number: '+233555123456', date_of_birth: null, relevant_medical_notes: '', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z' },
    ])
    vi.mocked(operations.getPatientMeasurements).mockResolvedValue([
      { id: 'm-1', patient: 'pat-123', device: 'dev-1', event_id: 'evt-1', measurement_type: 'heart_rate_bpm', value: '79', unit: 'bpm', source: 'device', quality: 'good', measured_at: '2025-01-01T00:00:00Z', received_at: '2025-01-01T00:00:00Z' },
    ])
    vi.mocked(operations.getPatientLocations).mockResolvedValue([
      { id: 'loc-1', patient: 'pat-123', device: 'dev-1', event_id: 'evt-2', latitude: '5.6508', longitude: '-0.1869', accuracy_meters: '10', source: 'gps', quality: 'good', recorded_at: '2025-01-01T00:00:00Z', received_at: '2025-01-01T00:00:00Z' },
    ])

    renderApp('/devices/dev-1')

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: 'NS-SIM-001' })).toBeInTheDocument()
    })

    expect(screen.getAllByText('Ada Mensah').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/79\b/i).length).toBeGreaterThan(0)
  })

  it('loads live wearable data from the backend when the demo route opens', async () => {
    const user: CurrentUser = {
      username: 'coordinator1',
      role: 'emergency_coordinator',
      can_access_operations: true,
    }

    vi.mocked(getAuthToken).mockReturnValue('token-1')
    mockApiRequest.mockResolvedValueOnce(user).mockResolvedValueOnce([])

    vi.mocked(operations.getPatients).mockResolvedValue([
      { id: 'pat-123', full_name: 'Ada Mensah', status: 'active', phone_number: '+233555123456', date_of_birth: null, relevant_medical_notes: '', created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z' },
    ])
    vi.mocked(operations.getPatientDevices).mockResolvedValue([
      { id: 'dev-1', device_identifier: 'NS-SIM-001', device_type: 'wearable', status: 'active', firmware_version: '1.0.0', battery_percent: 82, last_seen_at: '2025-01-01T00:00:00Z', last_seen_age_seconds: 12, is_stale: false, credential_revoked: false, created_at: '2025-01-01T00:00:00Z', updated_at: '2025-01-01T00:00:00Z' },
    ])
    vi.mocked(operations.getPatientMeasurements).mockResolvedValue([
      { id: 'm-1', patient: 'pat-123', device: 'dev-1', event_id: 'evt-1', measurement_type: 'heart_rate_bpm', value: '79', unit: 'bpm', source: 'device', quality: 'good', measured_at: '2025-01-01T00:00:00Z', received_at: '2025-01-01T00:00:00Z' },
    ])
    vi.mocked(operations.getPatientLocations).mockResolvedValue([
      { id: 'loc-1', patient: 'pat-123', device: 'dev-1', event_id: 'evt-2', latitude: '5.6508', longitude: '-0.1869', accuracy_meters: '10', source: 'gps', quality: 'good', recorded_at: '2025-01-01T00:00:00Z', received_at: '2025-01-01T00:00:00Z' },
    ])

    renderApp('/demo')

    await waitFor(() => {
      expect(operations.getPatients).toHaveBeenCalledTimes(1)
    })

    await waitFor(() => {
      expect(screen.getByText('79')).toBeInTheDocument()
    })
  })
})
