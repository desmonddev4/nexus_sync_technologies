import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, FocusEvent, FormEvent, KeyboardEvent, PointerEvent } from 'react'
import { AlertCircle, Camera, Eye, EyeOff, Lock, Radio, ShieldCheck, User, Zap } from 'lucide-react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import { apiRequest } from '../../api/client'
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
const FACE_TEST_UI_ENABLED = import.meta.env.VITE_BIOMETRIC_FACE_LOGIN_ENABLED === 'true'

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
  const { login, loginAndEnrollFace, token, user, isChecking } = useAuth()
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
  const [faceMode, setFaceMode] = useState<'password' | 'face' | 'enroll'>('password')
  const [faceConsent, setFaceConsent] = useState(false)
  const [faceFrames, setFaceFrames] = useState<Blob[]>([])
  const [faceChallenge, setFaceChallenge] = useState<{ challenge: string; steps: ('center' | 'left' | 'right')[] } | null>(null)
  const [cameraError, setCameraError] = useState('')
  const [formNotice, setFormNotice] = useState('')

  const usernameRef = useRef<HTMLInputElement>(null)
  const passwordRef = useRef<HTMLInputElement>(null)
  const videoRef = useRef<HTMLVideoElement>(null)
  const cameraStream = useRef<MediaStream | null>(null)

  const redirectTo = (location.state as RedirectState | null)?.from?.pathname || '/'

  // Redirect signed-in operators (done in an effect, not during render).
  useEffect(() => {
    if (token && user?.can_access_operations) {
      navigate(redirectTo, { replace: true })
    }
  }, [token, user, navigate, redirectTo])

  useEffect(() => {
    if (faceMode === 'password') return
    let active = true
    setCameraError('')
    setFaceFrames([])
    setFaceChallenge(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError('This browser does not support camera capture.')
      return () => { active = false }
    }
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      .then((stream) => {
        if (!active) { stream.getTracks().forEach((track) => track.stop()); return }
        cameraStream.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      })
      .catch(() => setCameraError('Camera access was unavailable. Allow camera permission and try again.'))
    return () => {
      active = false
      cameraStream.current?.getTracks().forEach((track) => track.stop())
      cameraStream.current = null
    }
  }, [faceMode])

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

    if (faceMode !== 'password' && (!faceChallenge || faceFrames.length !== 3)) {
      setFormError('Complete all three face prompts before continuing.')
      setShaking(true)
      return
    }
    if (faceMode === 'enroll' && !faceConsent) {
      setFormError('Consent is required to enroll a development face template.')
      setShaking(true)
      return
    }

    setSubmitting(true)
    try {
      if (faceMode === 'enroll' && faceChallenge) {
        await loginAndEnrollFace(username.trim(), password, { frames: faceFrames, challenge: faceChallenge.challenge })
        setFormNotice('Development face enrollment saved. Sign in with your username, password, and face capture to test it.')
        setFaceMode('password')
        setFaceConsent(false)
      } else {
        await login(username.trim(), password, faceMode === 'face' && faceChallenge ? { frames: faceFrames, challenge: faceChallenge.challenge } : undefined)
        navigate(redirectTo, { replace: true })
      }
    } catch (reason) {
      setFormError(reason instanceof Error ? reason.message : 'Sign-in failed. Check your credentials.')
      setShaking(true)
    } finally {
      setSubmitting(false)
    }
  }

  async function captureFace() {
    setCameraError('')
    if (!faceChallenge) {
      try {
        const challenge = await apiRequest<{ challenge: string; steps: ('center' | 'left' | 'right')[] }>('auth/face-liveness-challenge/')
        setFaceChallenge(challenge)
        setFaceFrames([])
      } catch (reason) {
        setCameraError(reason instanceof Error ? reason.message : 'Could not start the liveness challenge.')
      }
      return
    }
    if (faceFrames.length >= faceChallenge.steps.length) {
      setFaceChallenge(null)
      setFaceFrames([])
      setCameraError('Challenge cleared. Start again to capture a new sequence.')
      return
    }
    const video = videoRef.current
    if (!video || !video.videoWidth || !video.videoHeight) {
      setCameraError('Camera is starting. Try capture again in a moment.')
      return
    }
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const context = canvas.getContext('2d')
    if (!context) { setCameraError('Could not capture an image from the camera.'); return }
    context.drawImage(video, 0, 0)
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    if (!blob) { setCameraError('Could not capture an image from the camera.'); return }
    setFaceFrames((frames) => [...frames, blob])
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
      <section className={`login-form-panel${faceMode !== 'password' ? ' login-form-panel--face' : ''}`}>
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

            {FACE_TEST_UI_ENABLED && <div className="login-face-modes" aria-label="Sign-in method">
              <button type="button" className={faceMode === 'password' ? 'is-selected' : ''} onClick={() => { setFaceMode('password'); setFormNotice('') }}>Password</button>
              <button type="button" className={faceMode === 'face' ? 'is-selected' : ''} onClick={() => { setFaceMode('face'); setFormNotice('') }}>Face test</button>
              <button type="button" className={faceMode === 'enroll' ? 'is-selected' : ''} onClick={() => { setFaceMode('enroll'); setFormNotice('') }}>Enroll test face</button>
            </div>}

            {FACE_TEST_UI_ENABLED && faceMode !== 'password' && (
              <section className="login-face-panel" aria-label="Development face verification">
                <p>Development test only. Your password is still required. Follow the randomized head-turn prompts; this motion check is not production-validated.</p>
                <video ref={videoRef} autoPlay muted playsInline aria-label="Camera preview" />
                <button type="button" className="login-face-capture" onClick={captureFace} disabled={submitting}>
                  <Camera size={16} /> {!faceChallenge ? 'Start face-motion check' : faceFrames.length >= 3 ? 'Restart challenge' : `Capture ${faceChallenge.steps[faceFrames.length] ?? ''}`}
                </button>
                {faceChallenge && faceFrames.length < 3 && <span className="login-face-captured">{faceChallenge.steps[faceFrames.length] === 'center' ? 'Face the camera and capture.' : `Turn your head so your nose moves toward the ${faceChallenge.steps[faceFrames.length]} side of the preview, then capture.`}</span>}
                {faceFrames.length === 3 && <span className="login-face-captured">Challenge frames ready</span>}
                {cameraError && <p className="login-field-error" role="alert">{cameraError}</p>}
                {faceMode === 'enroll' && (
                  <label className="login-face-consent">
                    <input type="checkbox" checked={faceConsent} onChange={(event) => setFaceConsent(event.target.checked)} />
                    I consent to storing an encrypted face template for local development sign-in testing. I can remove it by deleting the enrollment.
                  </label>
                )}
              </section>
            )}

            {formNotice && <p className="login-face-notice" role="status">{formNotice}</p>}

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
              <span className="login-submit-label">{submitting ? 'Verifying…' : faceMode === 'face' ? 'Verify face & sign in' : faceMode === 'enroll' ? 'Enroll development face' : 'Sign in'}</span>
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
