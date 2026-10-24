import { createContext } from 'react'
import type { ReactNode } from 'react'
import type { CurrentUser } from '../types/api'

export interface AuthContextValue {
  token: string | null
  username: string | null
  user: CurrentUser | null
  isChecking: boolean
  login: (username: string, password: string, faceCapture?: { frames: Blob[]; challenge: string }) => Promise<void>
  loginAndEnrollFace: (username: string, password: string, faceCapture: { frames: Blob[]; challenge: string }) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
export type { ReactNode }
