import { Activity, Ambulance, ClipboardList, HeartPulse, LogOut, Users } from 'lucide-react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../../auth/useAuth'
import './AppShell.css'

const navigation = [
  { to: '/', label: 'Operations overview', icon: Activity, end: true },
  { to: '/incidents', label: 'Incident queue', icon: ClipboardList },
  { to: '/patients', label: 'Patients', icon: Users },
  { to: '/services', label: 'Emergency services', icon: Ambulance },
]

export function AppShell() {
  const { username, logout } = useAuth()
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <div className="app-brand">
          <span className="app-brand__mark"><HeartPulse size={20} /></span>
          <span><strong>NEXUS</strong><small>SYNC OPERATIONS</small></span>
        </div>
        <div className="app-sidebar__section">CONTROL ROOM</div>
        <nav className="app-nav" aria-label="Main navigation">
          {navigation.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => `app-nav__link${isActive ? ' is-active' : ''}`}>
              <Icon size={17} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="app-sidebar__bottom">
          <div className="app-session"><span className="app-session__dot" />API session active</div>
          <button className="app-logout" type="button" onClick={logout}><LogOut size={16} /> Sign out</button>
        </div>
      </aside>
      <div className="app-main">
        <header className="app-topbar">
          <div className="app-topbar__environment"><span /> PILOT ENVIRONMENT</div>
          <div className="app-topbar__user"><span className="app-avatar">{username?.slice(0, 1).toUpperCase() || 'O'}</span>{username || 'Operator'}</div>
        </header>
        <main className="app-content"><Outlet /></main>
      </div>
    </div>
  )
}