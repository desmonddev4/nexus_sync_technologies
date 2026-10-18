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
})
