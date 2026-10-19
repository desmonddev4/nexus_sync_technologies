import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { Patient } from '../../types/api'
import { PatientsPage } from './PatientsPage'

vi.mock('../../api/operations', () => ({
  getPatients: vi.fn(),
  getPatientDevices: vi.fn(),
  createPatient: vi.fn(),
}))

import { getPatientDevices, getPatients } from '../../api/operations'

const now = new Date().toISOString()

const mockPatients: Patient[] = [{
  id: 'patient-1',
  full_name: 'Jane Doe',
  phone_number: '+123456789',
  date_of_birth: '1990-01-01',
  relevant_medical_notes: 'Allergies: none',
  status: 'active',
  created_at: now,
  updated_at: now,
}]

describe('PatientsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows the patient device status and battery in each record', async () => {
    vi.mocked(getPatients).mockResolvedValue(mockPatients)
    vi.mocked(getPatientDevices).mockResolvedValue([
      {
        id: 'device-1',
        device_identifier: 'SIM-42',
        device_type: 'simulator',
        status: 'ready',
        firmware_version: '1.0.0',
        battery_percent: 72,
        last_seen_at: now,
        last_seen_age_seconds: 124,
        is_stale: false,
        credential_revoked: false,
        created_at: now,
        updated_at: now,
      },
    ])

    render(
      <MemoryRouter>
        <PatientsPage />
      </MemoryRouter>,
    )

    await waitFor(() => {
      expect(screen.getByText('Jane Doe')).toBeInTheDocument()
    })

    expect(screen.getByText('SIM-42')).toBeInTheDocument()
    expect(screen.getByText('ready')).toBeInTheDocument()
    expect(screen.getByText(/72%/)).toBeInTheDocument()
  })
})
