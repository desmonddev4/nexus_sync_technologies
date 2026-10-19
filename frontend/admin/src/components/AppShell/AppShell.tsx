import { useEffect, useRef, useState } from 'react'
import {
  Activity,
  Ambulance,
  Cpu,
  ClipboardList,
  HeartPulse,
  LogOut,
  MapPinned,
  ClipboardCheck,
  ScrollText,
  Settings2,
  Siren,
  UserCog,
  Users,
  BellRing,
  X,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import nstLogo from '../../assets/NST LOGO.png'
import alertToneAudio from '../../assets/alert-sound.mp4'
import { advanceIncident, getIncidents, getPatients } from '../../api/operations'
import type { Incident, Patient } from '../../types/api'
import './AppShell.css'

/* ------------------------------------------------------------------ */
/* Navigation                                                          */
/* ------------------------------------------------------------------ */

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  end?: boolean
}

interface NavGroup {
  title: string
  items: NavItem[]
}

const navigation: NavGroup[] = [
  {
    title: 'Control room',
    items: [
      { to: '/', label: 'Operations overview', icon: Activity, end: true },
      { to: '/demo', label: 'Wearable demo', icon: HeartPulse },
      { to: '/incidents', label: 'Incident queue', icon: ClipboardList },
      { to: '/patients', label: 'Patients', icon: Users },
      { to: '/devices', label: 'Devices', icon: Cpu },
      { to: '/services', label: 'Emergency services', icon: Ambulance },
      { to: '/map', label: 'Emergency map', icon: MapPinned },
    ],
  },
  {
    title: 'Safety and administration',
    items: [
      { to: '/monitoring/rules', label: 'Monitoring rules', icon: Siren },
      { to: '/monitoring/review', label: 'Measurement review', icon: ClipboardCheck },
      { to: '/audit/logs', label: 'Audit logs', icon: ScrollText },
      { to: '/accounts', label: 'Accounts', icon: UserCog },
      { to: '/settings', label: 'Settings', icon: Settings2 },
    ],
  },
]

/** Finds the nav entry that matches the current URL (longest match wins). */
function findCurrentPage(pathname: string) {
  let best: { group: string; label: string; length: number } | null = null
  for (const group of navigation) {
    for (const item of group.items) {
      const hit = item.end
        ? pathname === item.to
        : pathname === item.to || pathname.startsWith(`${item.to}/`)
      if (hit && (!best || item.to.length > best.length)) {
        best = { group: group.title, label: item.label, length: item.to.length }
      }
    }
  }
  return best
}

/* ------------------------------------------------------------------ */
/* Live clock for the topbar                                           */
/* ------------------------------------------------------------------ */

function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 15_000)
    return () => window.clearInterval(timer)
  }, [])
  return now
}

interface AlertToastEntry {
  id: string
  incidentId: string
  title: string
  patientName: string
  locationLabel: string
  detail: string
  priority: 'critical' | 'high' | 'medium' | 'low'
}

function getIncidentTitle(incident: Incident) {
  return incident.incident_type.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function getLocationSummary(incident: Incident) {
  if (!incident.location) {
    return 'No active location'
  }

  if (incident.location.is_stale) {
    return 'Location stale'
  }

  return 'Location active'
}

function AlertToastCenter() {
  const [toasts, setToasts] = useState<AlertToastEntry[]>([])
  const seenIdsRef = useRef<Set<string>>(new Set())
  const alertAudioRef = useRef<HTMLAudioElement | null>(null)

  const stopAlertTone = () => {
    const audio = alertAudioRef.current
    if (!audio) return
    if (typeof audio.pause === 'function') {
      audio.pause()
    }
    if ('currentTime' in audio) {
      audio.currentTime = 0
    }
    audio.onended = null
    alertAudioRef.current = null
  }

  const startAlertTone = () => {
    if (typeof window === 'undefined') return

    const audio = alertAudioRef.current ?? new Audio(alertToneAudio)
    audio.volume = 1
    audio.muted = false
    if ('currentTime' in audio) {
      audio.currentTime = 0
    }
    audio.onended = () => {
      if (alertAudioRef.current !== audio) return
      if (document.visibilityState === 'hidden') return
      if (typeof audio.play === 'function') {
        const playResult = audio.play()
        if (playResult && typeof playResult.catch === 'function') {
          playResult.catch(() => undefined)
        }
      }
    }

    alertAudioRef.current = audio
    if (typeof audio.play === 'function') {
      const playResult = audio.play()
      if (playResult && typeof playResult.catch === 'function') {
        playResult.catch(() => {
          const AudioCtor = window.AudioContext || (window as Window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
          if (!AudioCtor) return
          try {
            const audioContext = new AudioCtor()
            const oscillatorA = audioContext.createOscillator()
            const oscillatorB = audioContext.createOscillator()
            const gain = audioContext.createGain()

            oscillatorA.type = 'sawtooth'
            oscillatorB.type = 'square'
            oscillatorA.frequency.setValueAtTime(980, audioContext.currentTime)
            oscillatorA.frequency.exponentialRampToValueAtTime(420, audioContext.currentTime + 0.28)
            oscillatorB.frequency.setValueAtTime(640, audioContext.currentTime)
            oscillatorB.frequency.exponentialRampToValueAtTime(240, audioContext.currentTime + 0.35)

            gain.gain.setValueAtTime(0.0001, audioContext.currentTime)
            gain.gain.exponentialRampToValueAtTime(0.35, audioContext.currentTime + 0.02)
            gain.gain.exponentialRampToValueAtTime(0.0001, audioContext.currentTime + 0.7)

            oscillatorA.connect(gain)
            oscillatorB.connect(gain)
            gain.connect(audioContext.destination)

            oscillatorA.start()
            oscillatorB.start()
            oscillatorA.stop(audioContext.currentTime + 0.7)
            oscillatorB.stop(audioContext.currentTime + 0.7)
            void audioContext.resume()
          } catch {
            // Browser audio restrictions can be ignored when the device does not allow autoplay.
          }
        })
      }
    }
  }

  useEffect(() => {
    let active = true

    const pollAlerts = async () => {
      try {
        const [incidents, patients] = await Promise.all([getIncidents(), getPatients()])
        if (!active) return

        const patientMap = new Map<string, Patient>(patients.map((patient) => [patient.id, patient]))
        const freshIncidents = incidents.filter((incident) => {
          const isActive = !['resolved', 'closed', 'cancelled', 'declined'].includes(incident.status)
          return isActive && !seenIdsRef.current.has(incident.id)
        })

        if (freshIncidents.length === 0) {
          const knownIds = new Set(incidents.map((incident) => incident.id))
          seenIdsRef.current = knownIds
          return
        }

        const newToasts = freshIncidents.slice(0, 3).map((incident) => {
          const patient = patientMap.get(incident.patient)
          return {
            id: incident.id,
            incidentId: incident.id,
            title: getIncidentTitle(incident),
            patientName: patient?.full_name || 'Unknown patient',
            locationLabel: getLocationSummary(incident),
            detail: `${incident.trigger_source.toUpperCase()} alert • ${incident.priority.toUpperCase()} priority • ${incident.location ? 'Latest coordinates are live and tracked.' : 'No current location was available for this incident.'}`,
            priority: incident.priority as AlertToastEntry['priority'],
          }
        })

        setToasts((current) => {
          const merged = [...newToasts, ...current].slice(0, 3)
          if (merged.length > 0) {
            startAlertTone()
          }
          return merged
        })
        freshIncidents.forEach((incident) => seenIdsRef.current.add(incident.id))

        newToasts.forEach((toast) => {
          window.setTimeout(() => {
            setToasts((current) => current.filter((item) => item.id !== toast.id))
          }, 12_000)
        })
      } catch {
        // Ignore background polling failures; the incident queue remains the source of truth.
      }
    }

    void pollAlerts()
    const timer = window.setInterval(() => { void pollAlerts() }, 4_000)
    return () => {
      active = false
      stopAlertTone()
      window.clearInterval(timer)
    }
  }, [])

  useEffect(() => {
    if (toasts.length === 0) {
      stopAlertTone()
    } else {
      startAlertTone()
    }
  }, [toasts.length])

  const dismissToast = (id: string, nextStatus: 'resolved' | 'cancelled' = 'resolved') => {
    const toast = toasts.find((item) => item.id === id)
    if (toast) {
      void advanceIncident(toast.incidentId, nextStatus).catch(() => undefined)
    }

    setToasts((current) => current.filter((toastItem) => toastItem.id !== id))
  }

  if (toasts.length === 0) return null

  return (
    <div className="alert-toast-layer" aria-live="assertive" aria-atomic="true">
      <div className="alert-toast-backdrop" aria-hidden="true" />
      {toasts.map((toast) => (
        <div key={toast.id} className={`alert-toast alert-toast--${toast.priority}`} role="alert">
          <div className="alert-toast__topbar">
            <div className="alert-toast__label">
              <BellRing size={14} aria-hidden="true" />
              <span>Alert received</span>
            </div>
            <button type="button" className="alert-toast__close" onClick={() => dismissToast(toast.id)} aria-label="Dismiss alert alert">
              <X size={14} aria-hidden="true" />
            </button>
          </div>

          <div className="alert-toast__header">
            <strong>{toast.title}</strong>
            <span className="alert-toast__pill">{toast.priority}</span>
          </div>

          <dl className="alert-toast__details">
            <div>
              <dt>Patient</dt>
              <dd>{toast.patientName}</dd>
            </div>
            <div>
              <dt>Location status</dt>
              <dd>{toast.locationLabel}</dd>
            </div>
          </dl>

          <p className="alert-toast__detail">{toast.detail}</p>

          <div className="alert-toast__actions">
            <Link to="/incidents" className="alert-toast__open" onClick={() => dismissToast(toast.id, 'resolved')}>
              Open incident queue
            </Link>
            <button type="button" className="alert-toast__resolve" onClick={() => void dismissToast(toast.id, 'resolved')}>
              Mark resolved
            </button>
            <button type="button" className="alert-toast__cancel" onClick={() => void dismissToast(toast.id, 'cancelled')}>
              Cancel alert
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export function AppShell() {
  const { username, user, logout } = useAuth()
  const canManageProvisioning = user?.role === 'emergency_coordinator' || user?.role === 'superuser'
  const now = useClock()
  const { pathname } = useLocation()
  const page = findCurrentPage(pathname)
  const roleLabel = String(user?.role ?? 'operator').replaceAll('_', ' ')

  return (
    <div className="app-shell">
      <AlertToastCenter />
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand__mark">
            <img src={nstLogo} alt="" />
          </span>
          <span className="app-brand__text">
            <strong>Nexus Sync</strong>
            <small>Operations</small>
          </span>
        </div>

        <nav className="app-nav" aria-label="Main navigation">
          {navigation.map((group) => (
            <div className="app-nav__group" key={group.title}>
              <p className="app-sidebar__section">{group.title}</p>
              {group.items
                .filter(({ to }) => to !== '/devices' || canManageProvisioning)
                .map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    data-label={label}
                    className={({ isActive }) => `app-nav__link${isActive ? ' is-active' : ''}`}
                  >
                    <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                    <span>{label}</span>
                  </NavLink>
                ))}
            </div>
          ))}
        </nav>

        <div className="app-sidebar__bottom">
          <div className="app-session">
            <span className="app-session__dot" aria-hidden="true" />
            API session active
          </div>
          <button className="app-logout" type="button" onClick={logout} data-label="Sign out">
            <LogOut size={16} aria-hidden="true" />
            <span>Sign out</span>
          </button>
        </div>
      </aside>

      <div className="app-main">
        <header className="app-topbar">
          <div className="app-topbar__page">
            <span className="app-topbar__eyebrow">{page?.group ?? 'Nexus Sync'}</span>
            <div className="app-topbar__title">{page?.label ?? 'Console'}</div>
          </div>

          <div className="app-topbar__right">
            <div className="app-topbar__environment">
              <span aria-hidden="true" />
              Pilot environment
            </div>

            <span className="app-topbar__divider" aria-hidden="true" />

            <time className="app-topbar__clock" dateTime={now.toISOString()}>
              <strong>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong>
              <small>{now.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })}</small>
            </time>

            <span className="app-topbar__divider" aria-hidden="true" />

            <div className="app-topbar__user">
              <span className="app-avatar">{username?.slice(0, 1).toUpperCase() || 'O'}</span>
              <span className="app-topbar__who">
                <span className="app-topbar__name">{username || 'Operator'}</span>
                <span className="app-topbar__role">{roleLabel}</span>
              </span>
            </div>
          </div>
        </header>

        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}