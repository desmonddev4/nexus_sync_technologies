import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FocusEvent, FormEvent, KeyboardEvent, PointerEvent } from 'react'
import { AlertCircle, Eye, EyeOff, Lock, Radio, ShieldCheck, User, Zap } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import nstLogo from '../../assets/NST LOGO.png'
import './LoginPage.css'

/* ------------------------------------------------------------------ */
/* Types & helpers                                                     */
/* ------------------------------------------------------------------ */

interface RedirectState {
  from?: { pathname?: string }
}

type FieldName = 'username' | 'password'
type FieldErrors = Partial<Record<FieldName, string>>
type FieldFlags = Record<FieldName, boolean>

interface Ripple {
  id: number
  x: number
  y: number
}

const FEATURES = [
  { icon: Radio, label: 'Live alert coordination' },
  { icon: Zap, label: 'Faster dispatch decisions' },
  { icon: ShieldCheck, label: 'Audited, role-based access' },
]

function validateField(field: FieldName, value: string): string {
  if (field === 'username') {
    const trimmed = value.trim()
    if (!trimmed) return 'Enter your username.'
    if (trimmed.length < 3) return 'Username must be at least 3 characters.'
    return ''
  }
  if (!value) return 'Enter your password.'
  return ''
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export function LoginPage() {
  const { login, token, user, isChecking } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState<FieldFlags>({ username: false, password: false })
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({})
  const [formError, setFormError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [capsLock, setCapsLock] = useState(false)
  const [shaking, setShaking] = useState(false)
  const [ripple, setRipple] = useState<Ripple | null>(null)

  const usernameRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)

  const redirectTo = (location.state as RedirectState | null)?.from?.pathname || '/'

  // Redirect signed-in operators (done in an effect, not during render).
  useEffect(() => {
    if (token && user?.can_access_operations) {
      navigate(redirectTo, { replace: true })
    }
  }, [token, user, navigate, redirectTo])

  /* ---------------------------- handlers ---------------------------- */

  function handleChange(field: FieldName) {
    return (event: ChangeEvent<HTMLInputElement>) => {
      const value = event.target.value
      if (field === 'username') setUsername(value)
      else setPassword(value)

      setFormError('')
      // Once a field has been visited, validate live so errors clear as soon as they're fixed.
      if (touched[field]) {
        setFieldErrors((prev) => ({ ...prev, [field]: validateField(field, value) }))
      }
    }
  }

  function handleBlur(field: FieldName) {
    return (event: FocusEvent<HTMLInputElement>) => {
      setTouched((prev) => ({ ...prev, [field]: true }))
      setFieldErrors((prev) => ({ ...prev, [field]: validateField(field, event.target.value) }))
      if (field === 'password') setCapsLock(false)
    }
  }

  function handleCapsLock(event: KeyboardEvent<HTMLInputElement>) {
    setCapsLock(event.getModifierState('CapsLock'))
  }

  // Soft spotlight that follows the pointer across the glass card.
  function handleCardPointerMove(event: PointerEvent<HTMLElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    event.currentTarget.style.setProperty('--mx', `${event.clientX - rect.left}px`)
    event.currentTarget.style.setProperty('--my', `${event.clientY - rect.top}px`)
  }

  function handleButtonPointerDown(event: PointerEvent<HTMLButtonElement>) {
    const rect = event.currentTarget.getBoundingClientRect()
    setRipple({ id: Date.now(), x: event.clientX - rect.left, y: event.clientY - rect.top })
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting) return
    setFormError('')

    const errors: FieldErrors = {
      username: validateField('username', username),
      password: validateField('password', password),
    }
    setTouched({ username: true, password: true })
    setFieldErrors(errors)

    if (errors.username || errors.password) {
      setShaking(true)
      ;(errors.username ? usernameRef : passwordRef).current?.focus()
      return
    }

    setSubmitting(true)
    try {
      await login(username.trim(), password)
      navigate(redirectTo, { replace: true })
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : 'Sign-in failed. Check your credentials.')
      setShaking(true)
    } finally {
      setSubmitting(false)
    }
  }

  /* ----------------------------- render ----------------------------- */

  if (isChecking) {
    return (
      <main className="login-checking">
        <img className="login-checking-logo" src={nstLogo} alt="" />
        <span>Verifying operator access…</span>
      </main>
    )
  }

  const usernameInvalid = Boolean(touched.username && fieldErrors.username)
  const passwordInvalid = Boolean(touched.password && fieldErrors.password)

  return (
    <main className="login-page">
      {/* Animated backdrop */}
      <div className="login-bg" aria-hidden="true">
        <span className="login-blob login-blob--cyan" />
        <span className="login-blob login-blob--blue" />
        <span className="login-blob login-blob--violet" />
        <span className="login-grid" />
        <img className="login-watermark" src={nstLogo} alt="" />
      </div>

      {/* Brand panel */}
      <section className="login-brand-panel">
        <div className="login-brand">
          <img src={nstLogo} alt="" />
          <strong>Nexus Sync</strong>
        </div>

        <div className="login-hero">
          <div className="login-orbit" aria-hidden="true">
            <span className="login-ring login-ring--outer" />
            <span className="login-ring login-ring--inner" />
            <span className="login-orbit-dot login-orbit-dot--a" />
            <span className="login-orbit-dot login-orbit-dot--b" />
            <img className="login-orbit-logo" src={nstLogo} alt="Nexus Sync logo" />
          </div>

          <div className="login-brand-copy">
            <h1>
              Every alert.
              <br />
              <span>One clear response.</span>
            </h1>
            <p>Secure coordination for authorized emergency staff.</p>
          </div>

          <ul className="login-features">
            {FEATURES.map(({ icon: Icon, label }) => (
              <li key={label}>
                <Icon size={15} />
                {label}
              </li>
            ))}
          </ul>
        </div>

        <p className="login-pilot-label">UPSA pilot in Accra</p>
      </section>

      {/* Form panel */}
      <section className="login-form-panel">
        <div className="login-card" onPointerMove={handleCardPointerMove}>
          <form
            className={`login-form${shaking ? ' is-shaking' : ''}`}
            onSubmit={handleSubmit}
            onAnimationEnd={(event) => {
              if (event.currentTarget === event.target) setShaking(false)
            }}
            noValidate
          >
            <header className="login-card-head">
              <span className="login-card-logo">
                <img src={nstLogo} alt="" />
              </span>
              <div>
                <h2>Sign in to operations</h2>
                <p className="login-description">Use your authorized Nexus Sync account.</p>
              </div>
            </header>

            <div className={`login-field${usernameInvalid ? ' is-invalid' : ''}`}>
              <label htmlFor="username">Username</label>
              <div className="login-input-wrap">
                <User className="login-input-icon" size={17} />
                <input
                  ref={usernameRef}
                  id="username"
                  name="username"
                  autoComplete="username"
                  placeholder="e.g. kofi.mensah"
                  value={username}
                  onChange={handleChange('username')}
                  onBlur={handleBlur('username')}
                  aria-invalid={usernameInvalid}
                  aria-describedby="username-error"
                  disabled={submitting}
                  autoFocus
                />
              </div>
              <p className="login-field-error" id="username-error" role={usernameInvalid ? 'alert' : undefined}>
                {usernameInvalid && (
                  <>
                    <AlertCircle size={13} />
                    {fieldErrors.username}
                  </>
                )}
              </p>
            </div>

            <div className={`login-field${passwordInvalid ? ' is-invalid' : ''}`}>
              <label htmlFor="password">Password</label>
              <div className="login-input-wrap">
                <Lock className="login-input-icon" size={17} />
                <input
                  ref={passwordRef}
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={handleChange('password')}
                  onBlur={handleBlur('password')}
                  onKeyDown={handleCapsLock}
                  onKeyUp={handleCapsLock}
                  aria-invalid={passwordInvalid}
                  aria-describedby="password-error"
                  disabled={submitting}
                />
                <button
                  type="button"
                  className="login-toggle"
                  onClick={() => setShowPassword((visible) => !visible)}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              <p
                className={`login-field-error${!passwordInvalid && capsLock ? ' is-hint' : ''}`}
                id="password-error"
                role={passwordInvalid ? 'alert' : undefined}
              >
                {passwordInvalid ? (
                  <>
                    <AlertCircle size={13} />
                    {fieldErrors.password}
                  </>
                ) : (
                  capsLock && (
                    <>
                      <AlertCircle size={13} />
                      Caps Lock is on.
                    </>
                  )
                )}
              </p>
            </div>

            {formError && (
              <p className="login-error" role="alert">
                <AlertCircle size={16} />
                {formError}
              </p>
            )}

            <button
              type="submit"
              className={`login-submit${submitting ? ' is-loading' : ''}`}
              disabled={submitting}
              onPointerDown={handleButtonPointerDown}
            >
              {ripple && (
                <span
                  key={ripple.id}
                  className="login-ripple"
                  style={{ left: ripple.x, top: ripple.y }}
                  onAnimationEnd={() => setRipple(null)}
                />
              )}
              <span className="login-submit-label">{submitting ? 'Verifying…' : 'Sign in'}</span>
              <span className="login-submit-spinner" aria-hidden="true" />
            </button>

            <p className="login-security">
              <ShieldCheck size={13} />
              Access is restricted and audited.
            </p>
          </form>
        </div>
      </section>
    </main>
  )
}