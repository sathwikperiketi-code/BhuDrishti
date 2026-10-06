import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { ArrowLeft, Menu, X } from 'lucide-react'
import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { GlobalSearch } from './GlobalSearch'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'
import { navigationItem, primaryMobileRoutes, routeAvailableForRole, routeHref, type RouteId } from './navigation'
import type { SessionUser } from '../features/auth/session'
import { useDialogFocus } from './useDialogFocus'
import './app-shell.css'
import { isQaWorkspace } from '../lib/workspace'

interface AppShellProps {
  currentRoute: RouteId
  children: ReactNode
  token: string
  user: SessionUser
  onLogout: () => void
  developmentPreview?: boolean
}

export function AppShell({ currentRoute, children, token, user, onLogout, developmentPreview }: AppShellProps) {
  const preview = import.meta.env.DEV && Boolean(developmentPreview)
  const [collapsed, setCollapsed] = useState(() => window.localStorage.getItem('bd.sidebar.collapsed') === 'true')
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [logoutOpen, setLogoutOpen] = useState(false)
  const reduceMotion = useReducedMotion()
  const closeSearch = useCallback(() => setSearchOpen(false), [])
  const menuRef = useDialogFocus<HTMLDivElement>(mobileMenuOpen, () => setMobileMenuOpen(false))
  const logoutRef = useDialogFocus<HTMLDivElement>(logoutOpen, () => setLogoutOpen(false))
  const visibleMobileRoutes = primaryMobileRoutes.filter((route) => routeAvailableForRole(route, user.role))

  useEffect(() => window.localStorage.setItem('bd.sidebar.collapsed', String(collapsed)), [collapsed])
  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!preview && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setMobileMenuOpen(false)
        setSearchOpen(true)
      }
      if (event.key === 'Escape') setMobileMenuOpen(false)
    }
    window.addEventListener('keydown', handleShortcut)
    return () => window.removeEventListener('keydown', handleShortcut)
  }, [preview])

  return (
    <div className="bd-app">
      <a className="bd-skip-link" href="#main-content" onClick={(event) => { event.preventDefault(); document.getElementById('main-content')?.focus(); document.getElementById('main-content')?.scrollIntoView() }}>Skip to main content</a>
      <div className="bd-desktop-sidebar"><Sidebar currentRoute={currentRoute} collapsed={collapsed} onToggle={() => setCollapsed((value) => !value)} onRequestLogout={() => setLogoutOpen(true)} user={user} /></div>
      <div className="bd-app-column">
        <TopBar currentRoute={currentRoute} onOpenMenu={() => setMobileMenuOpen(true)} onOpenSearch={() => setSearchOpen(true)} onRequestLogout={() => setLogoutOpen(true)} user={user} token={token} searchOpen={searchOpen} developmentPreview={preview} />
        {isQaWorkspace && <div className="bd-qa-banner" role="note"><strong>Isolated QA workspace · Synthetic/test data</strong><span>These fixtures exercise the real processing APIs. Records and parcel boundaries are not authoritative.</span></div>}
        <main id="main-content" className="bd-main" tabIndex={-1}>{children}</main>
        <footer className="bd-app-footer">BhuDrishti AI · AI assists. Validation checks. Human verifies. Audit records. GIS visualizes. This prototype does not determine legal ownership.</footer>
      </div>

      <nav className="bd-mobile-bottom-nav" aria-label="Primary mobile navigation" style={{ gridTemplateColumns: `repeat(${visibleMobileRoutes.length + 1}, minmax(0, 1fr))` }}>
        {visibleMobileRoutes.map((route) => {
          const item = navigationItem(route)
          const Icon = item.icon
          return <a key={route} href={routeHref(route)} aria-current={currentRoute === route ? 'page' : undefined}><Icon size={19} strokeWidth={1.8} aria-hidden="true" /><span>{item.label === 'Command Center' ? 'Home' : item.label}</span></a>
        })}
        <button type="button" onClick={() => setMobileMenuOpen(true)} aria-label="More navigation"><Menu size={19} aria-hidden="true" /><span>More</span></button>
      </nav>

      {createPortal(<AnimatePresence>
        {mobileMenuOpen && (
          <div className="bd-mobile-drawer-layer">
            <motion.button type="button" className="bd-mobile-drawer-backdrop" aria-label="Close navigation menu" aria-hidden="true" tabIndex={-1} onClick={() => setMobileMenuOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: reduceMotion ? 0 : 0.16 }} />
            <motion.div ref={menuRef} className="bd-mobile-drawer" role="dialog" aria-modal="true" aria-label="Navigation menu" tabIndex={-1} initial={reduceMotion ? false : { x: '-100%' }} animate={{ x: 0 }} exit={reduceMotion ? {} : { x: '-100%' }} transition={{ duration: reduceMotion ? 0 : 0.23, ease: [0.2, 0.8, 0.2, 1] }}>
              <button className="bd-drawer-close" type="button" onClick={() => setMobileMenuOpen(false)} aria-label="Close navigation"><X size={20} aria-hidden="true" /></button>
              <Sidebar currentRoute={currentRoute} collapsed={false} onToggle={() => undefined} onNavigate={() => setMobileMenuOpen(false)} onRequestLogout={() => { setMobileMenuOpen(false); setLogoutOpen(true) }} user={user} mobile />
            </motion.div>
          </div>
        )}
      </AnimatePresence>, document.body)}

      {searchOpen && !preview && <GlobalSearch onClose={closeSearch} role={user.role} token={token} />}
      {logoutOpen && createPortal(
        <div className="bd-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) setLogoutOpen(false) }}>
          <div ref={logoutRef} className="bd-info-dialog" role="dialog" aria-modal="true" aria-labelledby="bd-logout-title" tabIndex={-1}>
            <div className="bd-info-dialog-icon"><ArrowLeft size={20} aria-hidden="true" /></div>
            <h2 id="bd-logout-title">Sign out</h2>
            <p>End the current session for {user.name}.</p>
            <button type="button" onClick={() => { setLogoutOpen(false); onLogout() }}>Sign out</button>
            <button type="button" className="bd-info-dialog-secondary" onClick={() => setLogoutOpen(false)}>Keep working</button>
          </div>
        </div>, document.body
      )}
    </div>
  )
}
