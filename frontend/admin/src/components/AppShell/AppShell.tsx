import { useEffect, useState } from 'react'
import {
  Activity,
  Ambulance,
  Cpu,
  ClipboardList,
  LogOut,
  MapPinned,
  ClipboardCheck,
  ScrollText,
  Settings2,
  Siren,
  UserCog,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import nstLogo from '../../assets/NST LOGO.png'
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