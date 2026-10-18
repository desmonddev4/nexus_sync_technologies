import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import { AppShell } from './components/AppShell/AppShell'
import { LoginPage } from './pages/LoginPage/LoginPage'
import { OverviewPage } from './pages/OverviewPage/OverviewPage'
import { IncidentsPage } from './pages/IncidentsPage/IncidentsPage'
import { IncidentDetailPage } from './pages/IncidentDetailPage/IncidentDetailPage'
import { PatientsPage } from './pages/PatientsPage/PatientsPage'
import { PatientDetailPage } from './pages/PatientDetailPage/PatientDetailPage'
import { MonitoringRulesPage } from './pages/MonitoringRulesPage/MonitoringRulesPage'
import { AuditLogsPage } from './pages/AuditLogsPage/AuditLogsPage'
import { AccountsPage } from './pages/AccountsPage/AccountsPage'
import { SettingsPage } from './pages/SettingsPage/SettingsPage'
import { ServicesPage } from './pages/ServicesPage/ServicesPage'
import { MeasurementReviewPage } from './pages/MeasurementReviewPage/MeasurementReviewPage'

const OperationsMapPage = lazy(() => import('./pages/OperationsMapPage/OperationsMapPage').then((module) => ({ default: module.OperationsMapPage })))

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route element={<ProtectedOperations />}>
            <Route element={<AppShell />}>
              <Route index element={<OverviewPage />} />
              <Route path="incidents" element={<IncidentsPage />} />
              <Route path="incidents/:incidentId" element={<IncidentDetailPage />} />
              <Route path="patients" element={<PatientsPage />} />
              <Route path="patients/:patientId" element={<PatientDetailPage />} />
              <Route path="monitoring/rules" element={<MonitoringRulesPage />} />
              <Route path="monitoring/review" element={<MeasurementReviewPage />} />
              <Route path="audit/logs" element={<AuditLogsPage />} />
              <Route path="accounts" element={<AccountsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="services" element={<ServicesPage />} />
              <Route path="map" element={<Suspense fallback={<main className="auth-checking">Loading emergency map…</main>}><OperationsMapPage /></Suspense>} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}

function ProtectedOperations() {
  const { token, user, isChecking } = useAuth()
  const location = useLocation()
  if (isChecking) return <main className="auth-checking">Checking operator access…</main>
  if (!token) return <Navigate to="/login" replace state={{ from: location }} />
  if (!user?.can_access_operations) {
    return <main className="access-denied"><h1>Access restricted</h1><p>Your account is not authorized for emergency operations.</p></main>
  }
  return <Outlet />
}

export default App
