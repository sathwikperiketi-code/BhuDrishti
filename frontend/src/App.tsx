import { motion, useReducedMotion } from 'framer-motion'
import { lazy, Suspense, useEffect, useState } from 'react'
import { AppShell } from './app/AppShell'
import { PlannedPage } from './app/PlannedPage'
import { routeAvailableForRole, routeFromHash, type RouteId } from './app/navigation'
import { RouteErrorBoundary } from './app/RouteErrorBoundary'
import { AccountPage } from './features/auth/AccountPages'
import { publicAuthRoute } from './features/auth/publicRoutes'
import { useSession, type SessionUser } from './features/auth/session'
import { isRevenueOfficerPreviewRoute } from './app/developmentRoutes'

const DevRevenueOfficerPortal = import.meta.env.DEV
  ? lazy(() => import('./features/dev/RevenueOfficerPortal'))
  : null

const DashboardPage = lazy(async () => ({ default: (await import('./features/dashboard')).DashboardPage }))
const AnalyticsPage = lazy(async () => ({ default: (await import('./features/analytics')).AnalyticsPage }))
const LiveDocumentPage = lazy(async () => ({ default: (await import('./features/live')).LiveDocumentPage }))
const ReviewQueuePage = lazy(async () => ({ default: (await import('./features/review/ReviewQueuePage')).ReviewQueuePage }))
const ReviewWorkspacePage = lazy(async () => ({ default: (await import('./features/review/ReviewWorkspacePage')).ReviewWorkspacePage }))
const AuditPage = lazy(async () => ({ default: (await import('./features/phase4/AuditPage')).AuditPage }))
const RecordsPage = lazy(async () => ({ default: (await import('./features/phase4/RecordsPage')).RecordsPage }))
const RecordPage = lazy(async () => ({ default: (await import('./features/phase4/RecordPage')).RecordPage }))
const GisPage = lazy(async () => ({ default: (await import('./features/phase4/GisPage')).GisPage }))
const SettingsPage = lazy(async () => ({ default: (await import('./features/settings/SettingsPage')).SettingsPage }))

function RouteLoading() {
  return (
    <div className="bd-route-loading" role="status" aria-label="Loading workspace view">
      <div className="bd-route-loading-title" />
      <div className="bd-route-loading-line" />
      <div className="bd-route-loading-grid"><div /><div /><div /></div>
    </div>
  )
}

function detailId(hash: string, prefix: string) {
  const path = hash.split('?')[0]
  const value = path.match(new RegExp(`^#/${prefix}/([^/]+)$`))?.[1]
  try { return value ? decodeURIComponent(value) : undefined } catch { return undefined }
}

function CurrentPage({ route, hash, token, user, expiresAt }: { route: RouteId; hash: string; token: string; user: SessionUser; expiresAt: string }) {
  switch (route) {
    case 'dashboard': return <DashboardPage token={token} role={user.role} />
    case 'documents': return <LiveDocumentPage initialView="document" token={token} canUpload={user.role === 'ADMIN' || user.role === 'REVENUE_OFFICER'} />
    case 'demo': return <LiveDocumentPage initialView="document" token={token} canUpload={false} dataset="sample" />
    case 'processing': return <LiveDocumentPage initialView="processing" token={token} canUpload={user.role === 'ADMIN' || user.role === 'REVENUE_OFFICER'} />
    case 'validation': return <LiveDocumentPage initialView="validation" token={token} canUpload={user.role === 'ADMIN' || user.role === 'REVENUE_OFFICER'} />
    case 'review-queue': return detailId(hash, 'review')
      ? <ReviewWorkspacePage token={token} user={user} recordId={detailId(hash, 'review')} />
      : <ReviewQueuePage token={token} user={user} />
    case 'records': return detailId(hash, 'records')
      ? <RecordPage token={token} user={user} recordId={detailId(hash, 'records')!} />
      : <RecordsPage token={token} user={user} />
    case 'audit': return <AuditPage token={token} user={user} recordId={detailId(hash, 'audit')} />
    case 'gis': return <GisPage token={token} user={user} recordId={new URLSearchParams(hash.split('?')[1] ?? '').get('record') ?? undefined} />
    case 'analytics': return <AnalyticsPage token={token} />
    case 'settings': return <SettingsPage user={user} expiresAt={expiresAt} token={token} />
    default: return <PlannedPage route={route} />
  }
}

function AuthenticatedApp() {
  const auth = useSession()
  const [hash, setHash] = useState(() => window.location.hash)
  const publicRoute = publicAuthRoute(hash)
  const route: RouteId = routeFromHash(hash)
  const pageKey = ['documents', 'processing', 'validation'].includes(route) ? 'document-workspace' : hash.split('?')[0]
  const reduceMotion = useReducedMotion()

  useEffect(() => {
    const updateRoute = () => {
      const current = window.location.hash
      if (new URLSearchParams(current.split('?')[1] ?? '').has('case')) {
        window.history.replaceState(null, '', current.split('?')[0])
      }
      setHash(window.location.hash)
    }
    window.addEventListener('hashchange', updateRoute)
    if (!window.location.hash.startsWith('#/')) {
      window.history.replaceState(null, '', '#/dashboard')
    }
    updateRoute()
    return () => window.removeEventListener('hashchange', updateRoute)
  }, [])

  useEffect(() => {
    if ((auth.state.phase === 'signedOut' || auth.state.phase === 'error') && !publicRoute) {
      window.location.replace('#/login')
    } else if (auth.state.phase === 'ready' && (publicRoute === 'login' || publicRoute === 'signup')) {
      window.location.replace('#/dashboard')
    }
  }, [auth.state.phase, publicRoute])

  useEffect(() => {
    if (auth.state.phase === 'ready' && !publicRoute && !routeAvailableForRole(route, auth.state.session.user.role)) {
      window.location.replace('#/dashboard')
    }
  }, [auth.state, publicRoute, route])

  if (publicRoute || auth.state.phase !== 'ready') return <AccountPage
    route={publicRoute ?? 'login'} hash={hash}
    loginLoading={auth.state.phase === 'loading'}
    loginMessage={auth.state.phase === 'error' ? auth.state.message : undefined}
    onSignIn={(email, password) => void auth.signIn(email, password)}
    onClearError={auth.clearError}
  />

  const { accessToken, expiresAt, user } = auth.state.session
  const authorizedRoute = routeAvailableForRole(route, user.role) ? route : 'dashboard'
  return (
    <AppShell currentRoute={authorizedRoute} token={accessToken} user={user} onLogout={auth.signOut}>
      <RouteErrorBoundary key={pageKey}>
        <Suspense fallback={<RouteLoading />}>
            <motion.div key={pageKey} initial={reduceMotion ? false : { opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: reduceMotion ? 0 : 0.22, ease: [0.2, 0.8, 0.2, 1] }}>
              <CurrentPage route={authorizedRoute} hash={hash} token={accessToken} user={user} expiresAt={expiresAt} />
            </motion.div>
        </Suspense>
      </RouteErrorBoundary>
    </AppShell>
  )
}

function DevelopmentRouteSwitch() {
  const [hash, setHash] = useState(() => window.location.hash)
  useEffect(() => {
    const update = () => setHash(window.location.hash)
    window.addEventListener('hashchange', update)
    return () => window.removeEventListener('hashchange', update)
  }, [])

  if (DevRevenueOfficerPortal && isRevenueOfficerPreviewRoute(hash, import.meta.env.DEV, window.location.hostname)) {
    return <Suspense fallback={<RouteLoading />}><DevRevenueOfficerPortal /></Suspense>
  }
  return <AuthenticatedApp />
}

export default function App() {
  return import.meta.env.DEV ? <DevelopmentRouteSwitch /> : <AuthenticatedApp />
}
