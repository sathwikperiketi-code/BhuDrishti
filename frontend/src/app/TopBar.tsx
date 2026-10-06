import { Bell, ChevronDown, Command, Menu, Search, Settings2, LogOut } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useHealth } from '../hooks/useHealth'
import type { SessionUser } from '../features/auth/session'
import { NotificationCenter } from '../features/phase4/NotificationCenter'
import { navigationItem, routeHref, type RouteId } from './navigation'
import { displayRoleName } from '../lib/roles'

interface TopBarProps {
  currentRoute: RouteId
  searchOpen: boolean
  onOpenMenu: () => void
  onOpenSearch: () => void
  onRequestLogout: () => void
  user: SessionUser
  token: string
  developmentPreview?: boolean
}

export function TopBar({ currentRoute, searchOpen, onOpenMenu, onOpenSearch, onRequestLogout, user, token, developmentPreview }: TopBarProps) {
  const preview = import.meta.env.DEV && Boolean(developmentPreview)
  const [panelState, setPanelState] = useState<{ route: RouteId; panel: 'notifications' | 'profile' } | null>(null)
  const { state } = useHealth()
  const item = navigationItem(currentRoute)
  const online = state.phase === 'ready' && state.data.status === 'ok'
  const openPanel = panelState?.route === currentRoute ? panelState.panel : null

  useEffect(() => {
    if (!searchOpen) return
    const frame = window.requestAnimationFrame(() => setPanelState(null))
    return () => window.cancelAnimationFrame(frame)
  }, [searchOpen])

  useEffect(() => {
    if (!openPanel) return
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPanelState(null)
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [openPanel])

  return (
    <header className="bd-topbar">
      <div className="bd-topbar-left">
        <button className="bd-topbar-icon bd-mobile-menu" type="button" onClick={onOpenMenu} aria-label="Open navigation menu"><Menu size={21} aria-hidden="true" /></button>
        <nav className="bd-breadcrumb" aria-label="Breadcrumb">
          <span>BhuDrishti AI</span><span className="bd-breadcrumb-separator" aria-hidden="true">/</span><strong>{item.label}</strong>
        </nav>
      </div>

      <div className="bd-topbar-actions">
        <button type="button" className="bd-search-trigger" disabled={preview} onClick={() => { setPanelState(null); onOpenSearch() }} aria-label="Search records and workspace" aria-keyshortcuts="Control+K Meta+K">
          <Search size={17} aria-hidden="true" /><span>Search workspace</span><kbd><Command size={11} aria-hidden="true" /> K</kbd>
        </button>
        <span className={`bd-system-chip ${online ? 'bd-system-chip-online' : state.phase === 'loading' ? 'bd-system-chip-checking' : 'bd-system-chip-offline'}`} role="status">
          <span className="bd-system-dot" />
          <span>{online ? 'API responding' : state.phase === 'loading' ? 'Checking API' : 'API unavailable'}</span>
        </span>
        <div className="bd-popover-anchor">
          <button type="button" className="bd-topbar-icon" disabled={preview} onClick={() => setPanelState(openPanel === 'notifications' ? null : { route: currentRoute, panel: 'notifications' })} aria-label="Notifications" aria-expanded={openPanel === 'notifications'} aria-controls="bd-notifications-panel">
            <Bell size={19} strokeWidth={1.75} aria-hidden="true" />
          </button>
          {openPanel === 'notifications' && !preview && (
            <div id="bd-notifications-panel" className="bd-topbar-popover bd-notifications-popover" role="region" aria-label="Notifications">
              <NotificationCenter token={token} user={user} onClose={() => setPanelState(null)} />
            </div>
          )}
        </div>
        <div className="bd-popover-anchor">
          <button type="button" className="bd-profile-trigger" onClick={() => setPanelState(openPanel === 'profile' ? null : { route: currentRoute, panel: 'profile' })} aria-label={`Open account menu for ${user.name}, ${displayRoleName(user.role)}`} aria-expanded={openPanel === 'profile'} aria-controls="bd-profile-panel">
            <span className="bd-avatar bd-topbar-avatar" aria-hidden="true">{user.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span><span className="bd-profile-copy"><span className="bd-profile-name">{user.name}</span><span className="bd-profile-role">{displayRoleName(user.role)}</span></span><ChevronDown size={14} aria-hidden="true" />
          </button>
          {openPanel === 'profile' && (
            <div id="bd-profile-panel" className="bd-topbar-popover bd-profile-popover" role="region" aria-label="Account menu">
              <div className="bd-profile-popover-head"><strong>{user.name}</strong><span className="bd-profile-menu-role">{displayRoleName(user.role)}</span><span>{user.email}</span></div>
              <a href={routeHref('settings')} onClick={() => setPanelState(null)}><Settings2 size={16} aria-hidden="true" />Settings</a>
              <button type="button" onClick={() => { setPanelState(null); onRequestLogout() }}><LogOut size={16} aria-hidden="true" />Log out</button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
