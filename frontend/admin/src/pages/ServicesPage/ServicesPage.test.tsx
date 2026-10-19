import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ServicesPage } from './ServicesPage'

const { api, auth } = vi.hoisted(() => ({
  api: {
    getProviders: vi.fn(), getFacilities: vi.fn(), getVehicles: vi.fn(),
    getManagedProviders: vi.fn(), getManagedFacilities: vi.fn(), getManagedVehicles: vi.fn(),
    createManagedProvider: vi.fn(), createManagedFacility: vi.fn(), createManagedVehicle: vi.fn(),
    verifyManagedProvider: vi.fn(), verifyManagedFacility: vi.fn(),
  },
  auth: { useAuth: vi.fn() },
}))

vi.mock('../../api/operations', () => api)
vi.mock('../../auth/useAuth', () => auth)

describe('ServicesPage directory administration', () => {
  beforeEach(() => {
    Object.values(api).forEach((mock) => mock.mockReset())
    auth.useAuth.mockReturnValue({ user: { username: 'dispatch', role: 'emergency_coordinator' } })
    api.getProviders.mockResolvedValue([])
    api.getFacilities.mockResolvedValue([])
    api.getVehicles.mockResolvedValue([])
    api.getManagedProviders.mockResolvedValue([])
    api.getManagedFacilities.mockResolvedValue([])
    api.getManagedVehicles.mockResolvedValue([])
    api.createManagedProvider.mockResolvedValue({ id: 'provider-1' })
    api.createManagedFacility.mockResolvedValue({ id: 'facility-1' })
    api.createManagedVehicle.mockResolvedValue({ id: 'vehicle-1' })
    api.verifyManagedProvider.mockResolvedValue({ verification_status: 'verified' })
    api.verifyManagedFacility.mockResolvedValue({ verification_status: 'verified' })
  })

  it('allows coordinators to create a provider as pending, never pre-verified', async () => {
    render(<ServicesPage />)
    fireEvent.click(await screen.findByText('Add provider'))
    fireEvent.change(screen.getByLabelText('Provider name'), { target: { value: 'Accra Response' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create pending provider' }))

    await waitFor(() => expect(api.createManagedProvider).toHaveBeenCalledWith(expect.objectContaining({
      name: 'Accra Response', provider_type: 'private_ambulance',
    })))
    expect(await screen.findByRole('status')).toHaveTextContent(/remains unverified/i)
  })

  it('requires a recorded source before verification', async () => {
    api.getManagedProviders.mockResolvedValue([{ id: 'provider-1', name: 'Pending Provider', verification_status: 'unverified', verification_source: '', dispatch_phone_number: '' }])
    render(<ServicesPage />)
    const verify = await screen.findByRole('button', { name: /verify/i })
    fireEvent.click(verify)

    expect(api.verifyManagedProvider).not.toHaveBeenCalled()
    expect(await screen.findByRole('alert')).toHaveTextContent(/verification source/i)
    fireEvent.change(screen.getByLabelText('Verification source for Pending Provider'), { target: { value: 'Dispatch office phone confirmation' } })
    fireEvent.click(verify)
    await waitFor(() => expect(api.verifyManagedProvider).toHaveBeenCalledWith('provider-1', 'Dispatch office phone confirmation'))
  })

  it('does not expose management controls to clinicians', async () => {
    auth.useAuth.mockReturnValue({ user: { username: 'clinician', role: 'clinician' } })
    render(<ServicesPage />)

    expect(await screen.findByRole('heading', { name: 'Emergency services' })).toBeInTheDocument()
    expect(screen.queryByText('Directory administration')).not.toBeInTheDocument()
    expect(api.getManagedProviders).not.toHaveBeenCalled()
  })
})