import { ArrowRight, Bell, Check, CheckCheck, RefreshCw } from 'lucide-react'
import { useCallback, useState } from 'react'
import { phase4Api } from './api'
import { displayDate, eventLabel, eventTone, recordHref } from './format'
import type { NotificationItem, Phase4PageProps } from './types'
import { usePhase4Data } from './usePhase4Data'
import { displayRoleName } from '../../lib/roles'
import './phase4.css'

function destination(item: NotificationItem): string {
  if (item.href?.startsWith('#/')) return item.href
  if (item.recordId && (item.eventType.includes('REVIEW') || item.eventType.includes('CONFLICT'))) return `#/review/${encodeURIComponent(item.recordId)}`
  if (item.recordId) return recordHref(item.recordId)
  return '#/audit'
}

export function NotificationCenter({ token, user, onClose }: Phase4PageProps & { onClose?: () => void }) {
  const load = useCallback((signal: AbortSignal) => phase4Api.notifications(token, signal), [token])
  const { state, retry } = usePhase4Data(`notifications:${token}`, load)
  const [readOverride, setReadOverride] = useState<{ token: string; ids: string[] }>({ token: '', ids: [] })
  const [pending, setPending] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState('')
  const overrides = readOverride.token === token ? readOverride.ids : []
  const items = state.phase === 'ready' ? state.data.items : []
  const unread = items.filter((item) => !item.read && !overrides.includes(item.id))

  const markRead = useCallback(async (id: string) => {
    setPending(id)
    setError(null)
    setSuccess('')
    try {
      await phase4Api.markNotificationRead(token, id)
      setReadOverride((current) => ({ token, ids: [...new Set([...(current.token === token ? current.ids : []), id])] }))
      setSuccess('Notification marked as read.')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Mark as read failed. Please retry.')
    } finally { setPending(null) }
  }, [token])

  const markAllRead = useCallback(async () => {
    setPending('all')
    setError(null)
    setSuccess('')
    const results = await Promise.allSettled(unread.map((item) => phase4Api.markNotificationRead(token, item.id)))
    const succeeded = unread.filter((_, index) => results[index]?.status === 'fulfilled').map((item) => item.id)
    setReadOverride((current) => ({ token, ids: [...new Set([...(current.token === token ? current.ids : []), ...succeeded])] }))
    if (succeeded.length > 0) setSuccess(`${succeeded.length} loaded notification${succeeded.length === 1 ? '' : 's'} marked as read.`)
    if (succeeded.length !== unread.length) setError('Some notifications could not be marked as read. Retry the remaining items.')
    setPending(null)
  }, [token, unread])

  return <div className="p4-notifications" role="region" aria-label="Notifications">
    <div className="p4-notifications-head"><div><span className="p4-eyebrow">Workflow alerts</span><h2>Notifications {unread.length > 0 && <span className="p4-notification-count" aria-label={`${unread.length} unread`}>{unread.length}</span>}</h2></div><div className="p4-notification-head-actions">{unread.length > 0 && <button type="button" className="p4-mark-all" disabled={pending !== null} onClick={() => void markAllRead()}><CheckCheck size={14} aria-hidden="true" />Mark all read</button>}<button type="button" className="p4-icon-button" onClick={retry} aria-label="Refresh notifications"><RefreshCw size={15} aria-hidden="true" /></button></div></div>
    {error && <div className="p4-notification-error" role="alert">{error}</div>}
    {success && <div className="p4-notification-success" role="status">{success}</div>}
    {state.phase === 'loading' && <div className="p4-loading" role="status"><span className="p4-spinner" />Loading stored workflow notifications…</div>}
    {state.phase === 'error' && <div className="p4-error" role="alert"><strong>Notifications unavailable</strong><span>{state.error}</span><button type="button" onClick={retry}>Retry</button></div>}
    {state.phase === 'ready' && items.length === 0 && <div className="p4-empty p4-notifications-empty"><Bell size={21} aria-hidden="true" /><strong>No workflow notifications</strong><span>Recorded processing failures, relevant conflicts, assignments, and decisions appear here when available for your current access.</span></div>}
    {state.phase === 'ready' && items.length > 0 && <p className="p4-notification-scope">Showing {items.length} loaded alerts. Mark all read applies to this list.</p>}
    {state.phase === 'ready' && items.length > 0 && <ol className="p4-notification-list">{items.map((item) => {
      const read = Boolean(item.read || overrides.includes(item.id))
      return <li key={item.id} className={read ? 'p4-notification-read' : 'p4-notification-unread'}><div className="p4-notification-row"><a className="p4-notification-link" href={destination(item)} onClick={() => { if (!read) void markRead(item.id); onClose?.() }}><span className={`p4-mini-dot p4-mini-dot--${eventTone(item.eventType)}`} /><span><strong>{item.title || eventLabel(item.eventType)}</strong><small>{item.description}</small><time dateTime={item.timestamp} title={displayDate(item.timestamp)}>{displayDate(item.timestamp)}</time></span><ArrowRight size={14} aria-hidden="true" /></a>{!read && <button type="button" className="p4-notification-mark" disabled={pending !== null} onClick={() => void markRead(item.id)} aria-label={`Mark ${item.title || eventLabel(item.eventType)} as read`} title="Mark as read"><Check size={14} aria-hidden="true" /></button>}</div></li>
    })}</ol>}
    <div className="p4-notifications-foot"><span>{displayRoleName(user.role)} · {user.name}</span>{user.role !== 'VERIFIER' && <a href="#/audit" onClick={onClose}>Open audit trail <ArrowRight size={13} aria-hidden="true" /></a>}</div>
  </div>
}
