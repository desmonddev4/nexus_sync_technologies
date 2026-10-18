import { useEffect, useMemo, useState } from 'react'
import { apiRequest, clearAuthToken, getAuthToken, saveAuthToken } from '../api/client'
import type { CurrentUser } from '../types/api'
import { AuthContext } from './context'
import type { AuthContextValue, ReactNode } from './context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [initialToken] = useState<string | null>(() => getAuthToken())
  const [token, setToken] = useState<string | null>(initialToken)
  const [username, setUsername] = useState<string | null>(null)
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [isChecking, setIsChecking] = useState(Boolean(initialToken))

  useEffect(() => {
    if (!initialToken) return
    let active = true
    Promise.resolve()
      .then(() => apiRequest<CurrentUser>('auth/me/'))
      .then((currentUser) => {
        if (!active) return
        if (!currentUser.can_access_operations) {
          clearAuthToken()
          setToken(null)
          setUsername(null)
          setUser(null)
          return
        }
        setUsername(currentUser.username)
        setUser(currentUser)
      })
      .catch(() => {
        if (!active) return
        clearAuthToken()
        setToken(null)
        setUsername(null)
        setUser(null)
      })
      .finally(() => {
        if (active) setIsChecking(false)
      })
    return () => { active = false }
  }, [initialToken])

  async function login(usernameInput: string, password: string) {
    setIsChecking(true)
    try {
      const response = await apiRequest<{ token: string }>('auth/token/', {
        method: 'POST',
        body: JSON.stringify({ username: usernameInput, password }),
      })
      saveAuthToken(response.token)
      const currentUser = await apiRequest<CurrentUser>('auth/me/')
      if (!currentUser.can_access_operations) {
        throw new Error('This account is not authorized for the operations dashboard.')
      }
      setToken(response.token)
      setUsername(currentUser.username || usernameInput)
      setUser(currentUser)
    } catch (error) {
      clearAuthToken()
      setToken(null)
      setUsername(null)
      setUser(null)
      throw error
    } finally {
      setIsChecking(false)
    }
  }

  function logout() {
    clearAuthToken()
    setToken(null)
    setUsername(null)
    setUser(null)
    setIsChecking(false)
  }

  const value: AuthContextValue = useMemo(
    () => ({ token, username, user, isChecking, login, logout }),
    [token, username, user, isChecking],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
