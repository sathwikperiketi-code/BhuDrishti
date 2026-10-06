import { ChevronLeft, ChevronRight, LogOut, Settings2 } from 'lucide-react'
import { Brand } from '../components/Brand'
import { displayRoleName } from '../lib/roles'
import { navigationItems, navigationItem, routeAvailableForRole, routeHref, type RouteId } from './navigation'
import type { SessionUser } from '../features/auth/session'
import type { KeyboardEvent } from 'react'

interface SidebarProps {
  currentRoute: RouteId
  collapsed: boolean
  onToggle: () => void
  onNavigate?: () => void
  onRequestLogout: () => void
  user: SessionUser
  mobile?: boolean
}

const groups = [
  { id: 'operations', label: 'Operations' },
  { id: 'intelligence', label: 'Intelligence' },
] as const

export function Sidebar({ currentRoute, collapsed, onToggle, onNavigate, onRequestLogout, user, mobile = false }: SidebarProps) {
  const compact = collapsed && !mobile
  function navigateWithKeyboard(event: KeyboardEvent<HTMLElement>) {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return
    const links = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('.bd-sidebar-link'))
    const index = links.indexOf(event.target as HTMLElement)
    if (index < 0) return
    event.preventDefault()
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? links.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length
    links[next]?.focus()
  }

  return (
    <aside className={`bd-sidebar ${compact ? 'bd-sidebar-collapsed' : ''} ${mobile ? 'bd-sidebar-mobile' : ''}`} aria-label="Application sidebar" onKeyDown={navigateWithKeyboard}>
      <div className="bd-sidebar-brand">
        <a href={routeHref('dashboard')} onClick={onNavigate} aria-label="BhuDrishti AI Command Center">
          <Brand iconOnly={compact} />
        </a>
        {!mobile && (
          <button className="bd-sidebar-toggle" type="button" onClick={onToggle} aria-label={compact ? 'Expand sidebar' : 'Collapse sidebar'} title={compact ? 'Expand sidebar' : 'Collapse sidebar'}>
            {compact ? <ChevronRight size={17} aria-hidden="true" /> : <ChevronLeft size={17} aria-hidden="true" />}
          </button>
        )}
      </div>

      <div className="bd-sidebar-scroll">
        {groups.map((group) => (
          <nav key={group.id} className="bd-sidebar-group" aria-label={group.label}>
            <p className="bd-sidebar-group-label">{compact ? '·' : group.label}</p>
            <ul>
              {navigationItems.filter((item) => item.group === group.id && routeAvailableForRole(item.id, user.role)).map((item) => {
                const Icon = item.icon
                return (
                  <li key={item.id}>
                    <a
                      href={routeHref(item.id)}
                      className={`bd-sidebar-link ${currentRoute === item.id ? 'bd-sidebar-link-active' : ''}`}
                      aria-current={currentRoute === item.id ? 'page' : undefined}
                      aria-label={item.label}
                      onClick={onNavigate}
                      title={compact ? item.label : undefined}
                    >
                      <Icon size={18} strokeWidth={1.75} aria-hidden="true" />
                      {!compact && <span className="bd-sidebar-link-label">{item.label}</span>}
                      {!compact && item.phase === 'planned' && <span className="bd-sidebar-planned" aria-label="Planned module">Soon</span>}
                    </a>
                  </li>
                )
              })}
            </ul>
          </nav>
        ))}
      </div>

      <div className="bd-sidebar-footer">
        <div className="bd-prototype-label" title={compact ? 'Prototype backed by persisted records' : undefined}>
          <span className="bd-prototype-dot" />
          {!compact && <span>PROTOTYPE · SOURCE BACKED</span>}
        </div>
        <div className="bd-sidebar-identity" title={compact ? `${user.name} · ${displayRoleName(user.role)}` : undefined}>
          <span className="bd-avatar" aria-hidden="true">{user.name.split(' ').map((part) => part[0]).join('').slice(0, 2)}</span>
          {!compact && <span className="bd-identity-copy"><strong>{user.name}</strong><small>{displayRoleName(user.role)}</small></span>}
        </div>
        <a href={routeHref('settings')} aria-label="Settings" onClick={onNavigate} className={`bd-sidebar-link bd-sidebar-account-link ${currentRoute === 'settings' ? 'bd-sidebar-link-active' : ''}`} title={compact ? 'Settings' : undefined} aria-current={currentRoute === 'settings' ? 'page' : undefined}>
          <Settings2 size={18} strokeWidth={1.75} aria-hidden="true" />{!compact && <span>Settings</span>}
        </a>
        <button type="button" aria-label="Log out" className="bd-sidebar-link bd-sidebar-account-link" onClick={onRequestLogout} title={compact ? 'Log out' : undefined}>
          <LogOut size={18} strokeWidth={1.75} aria-hidden="true" />{!compact && <span>Log out</span>}
        </button>
      </div>
      <span className="sr-only">Current section: {navigationItem(currentRoute).label}</span>
    </aside>
  )
}
