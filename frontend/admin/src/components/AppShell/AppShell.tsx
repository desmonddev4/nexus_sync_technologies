import { useEffect, useState } from 'react'
import {
  Activity,
  Ambulance,
  ClipboardList,
  LogOut,
  ScrollText,
  Settings2,
  Siren,
  UserCog,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
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
      { to: '/services', label: 'Emergency services', icon: Ambulance },
    ],
  },
  {
    title: 'Safety and administration',
    items: [
      { to: '/monitoring/rules', label: 'Monitoring rules', icon: Siren },
      { to: '/audit/logs', label: 'Audit logs', icon: ScrollText },
      { to: '/accounts', label: 'Accounts', icon: UserCog },
      { to: '/settings', label: 'Settings', icon: Settings2 },
    ],
  },
]

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
  const { username, logout } = useAuth()
  const now = useClock()

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
              {group.items.map(({ to, label, icon: Icon, end }) => (
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
            <span className="app-session__dot" />
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
          <div className="app-topbar__environment">
            <span aria-hidden="true" />
            Pilot environment
          </div>

          <div className="app-topbar__right">
            <time className="app-topbar__clock" dateTime={now.toISOString()}>
              <strong>{now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</strong>
              <small>{now.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' })}</small>
            </time>
            <div className="app-topbar__user">
              <span className="app-avatar">{username?.slice(0, 1).toUpperCase() || 'O'}</span>
              <span className="app-topbar__name">{username || 'Operator'}</span>
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