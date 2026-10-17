import { useState } from 'react'
import type { FormEvent } from 'react'
import { Activity, HeartPulse, LockKeyhole } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import './LoginPage.css'

interface RedirectState {
  from?: { pathname?: string }
}

export function LoginPage() {
  const { login, token, user, isChecking } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (token && user?.can_access_operations) {
    const from = (location.state as RedirectState | null)?.from?.pathname || '/'
    navigate(from, { replace: true })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError('')
    setSubmitting(true)
    try {
      await login(username.trim(), password)
      const from = (location.state as RedirectState | null)?.from?.pathname || '/'
      navigate(from, { replace: true })
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Sign-in failed. Check your credentials.')
    } finally {
      setSubmitting(false)
    }
  }

  if (isChecking) return <main className="login-checking">Verifying operator access…</main>

  return (
    <main className="login-page">
      <section className="login-brand-panel">
        <div className="login-brand"><span><HeartPulse size={22} /></span><strong>NEXUS SYNC</strong></div>
        <div className="login-brand-copy">
          <p className="login-kicker"><Activity size={14} /> EMERGENCY OPERATIONS</p>
          <h1>Every alert.<br />One clear response.</h1>
          <p>Secure coordination for authorized emergency staff.</p>
        </div>
        <div className="login-pilot-label">UPSA PILOT · ACCRA</div>
      </section>
      <section className="login-form-panel">
        <form className="login-form" onSubmit={handleSubmit}>
          <span className="login-form-icon"><LockKeyhole size={18} /></span>
          <p className="login-kicker">STAFF ACCESS</p>
          <h2>Sign in to operations</h2>
          <p className="login-description">Use your authorized Nexus Sync account.</p>
          <label htmlFor="username">Username</label>
          <input id="username" name="username" autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required />
          {error && <p className="login-error" role="alert">{error}</p>}
          <button type="submit" disabled={submitting}>
            {submitting ? 'Verifying…' : 'Sign in'}
          </button>
          <p className="login-security">Access is restricted and audited.</p>
        </form>
      </section>
    </main>
  )
}