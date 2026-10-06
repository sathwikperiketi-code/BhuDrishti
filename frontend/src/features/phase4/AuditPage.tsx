import { ArrowLeft, ChevronLeft, ChevronRight, FileClock, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { phase4Api } from './api'
import { AuditTimeline } from './AuditTimeline'
import { eventLabel, recordHref } from './format'
import type { Phase4PageProps } from './types'
import { usePhase4Data } from './usePhase4Data'
import { displayRoleName } from '../../lib/roles'
import './phase4.css'

const eventFilters = [
  { value: '', label: 'All events' },
  { value: 'REVIEW_STARTED', label: 'Review started' },
  { value: 'FIELD_EDITED', label: 'Field corrections' },
  { value: 'FIELD_REJECTED', label: 'Field rejections' },
  { value: 'ISSUE_RESOLVED', label: 'Validation finding resolutions' },
  { value: 'REVIEW_RECOMMENDED', label: 'Recommendations' },
  { value: 'RECORD_APPROVED', label: 'Approvals' },
  { value: 'RECORD_REJECTED', label: 'Rejections' },
  { value: 'RECORD_SENT_BACK', label: 'Send back decisions' },
  { value: 'GEOMETRY_IMPORTED', label: 'Geometry imports' },
  { value: 'GEOMETRY_REPLACED', label: 'Geometry replacements' },
  { value: 'GIS_INDEXED', label: 'GIS indexing' },
]
const pageSize = 20

export function AuditPage({ token, user, recordId }: Phase4PageProps & { recordId?: string }) {
  const [eventType, setEventType] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)
  const load = useCallback((signal: AbortSignal) => phase4Api.audit(token, { recordId, eventType, limit: pageSize, offset: page * pageSize }, signal), [token, recordId, eventType, page])
  const { state, retry } = usePhase4Data(`audit:${token}:${recordId || 'all'}:${eventType}:${page}`, load)
  const events = useMemo(() => state.phase !== 'ready' ? [] : state.data.items.filter((event) => {
    const needle = search.trim().toLowerCase()
    return !needle || [event.description, event.eventType, eventLabel(event), event.actorName, event.actorId, displayRoleName(event.actorRole), event.recordId, typeof event.metadata?.reason === 'string' ? event.metadata.reason : ''].some((value) => value?.toLowerCase().includes(needle))
  }), [state, search])

  return <section className="p4-page p4-audit-page">
    <header className="p4-page-header"><div><span className="p4-eyebrow">Governance / stored workflow history</span><h1>{recordId ? 'Record audit trail' : 'Audit trail'}</h1><p>Inspect recorded actors, roles, timestamps, actions, reasons, and results from document processing, human review, and GIS imports.</p></div><span className="p4-header-symbol"><FileClock size={24} aria-hidden="true" /></span></header>
    {recordId ? <div className="p4-inline-bar"><a href="#/audit"><ArrowLeft size={15} aria-hidden="true" /> All events</a><span>Record <strong>{recordId}</strong></span><a href={recordHref(recordId)}>Open record</a></div> : null}
    <div className="p4-audit-layout"><aside className="p4-audit-sidebar p4-card"><div className="p4-card-heading"><span className="p4-eyebrow">Explore events</span><h2>History filters</h2></div><label className="p4-label" htmlFor="p4-audit-search">Search visible page</label><div className="p4-search"><Search size={16} aria-hidden="true" /><input id="p4-audit-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Action, actor, reason, record…" /></div><p className="p4-audit-search-note">Search applies to this page. Use event filters or Next/Previous to inspect the remaining history.</p><label className="p4-label" htmlFor="p4-audit-type">Event type</label><select id="p4-audit-type" value={eventType} onChange={(event) => { setEventType(event.target.value); setPage(0); setSearch('') }}>{eventFilters.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select><div className="p4-audit-sidebar-note"><ShieldCheck size={16} aria-hidden="true" /><span>These persisted events cannot be edited from this application view. This is not a cryptographically immutable ledger.</span></div><div className="p4-actor-chip">Viewing as <strong>{user.name}</strong> · {displayRoleName(user.role)}</div></aside>
      <div className="p4-audit-main"><div className="p4-section-heading"><div><span className="p4-eyebrow">Activity stream</span><h2>{state.phase === 'ready' ? `${state.data.total} event${state.data.total === 1 ? '' : 's'} recorded` : state.phase === 'loading' ? 'Loading history' : 'History unavailable'}</h2></div><button className="p4-icon-button" type="button" onClick={retry} aria-label="Refresh audit events"><RefreshCw size={16} aria-hidden="true" /></button></div>
        {state.phase === 'loading' ? <div className="p4-loading" role="status"><span className="p4-spinner" />Loading audit history…</div> : null}
        {state.phase === 'error' ? <div className="p4-error" role="alert"><strong>Audit history is unavailable</strong><span>{state.error}</span><button type="button" onClick={retry}>Retry</button></div> : null}
        {state.phase === 'ready' && events.length === 0 && search ? <div className="p4-empty"><Search size={24} aria-hidden="true" /><strong>No matching events on this page</strong><span>Try another action, actor, reason, or record identifier. Other pages may contain more matching history.</span></div> : null}
        {state.phase === 'ready' && (events.length > 0 || !search) ? <AuditTimeline events={events} showRecordLinks={!recordId} /> : null}
        {state.phase === 'ready' && state.data.total > pageSize ? <nav className="p4-audit-pagination" aria-label="Audit history pages"><span>Showing {page * pageSize + 1}–{Math.min((page + 1) * pageSize, state.data.total)} of {state.data.total}</span><div><button type="button" disabled={page === 0} onClick={() => { setPage((value) => value - 1); setSearch('') }}><ChevronLeft size={15} aria-hidden="true" />Previous</button><button type="button" disabled={(page + 1) * pageSize >= state.data.total} onClick={() => { setPage((value) => value + 1); setSearch('') }}>Next<ChevronRight size={15} aria-hidden="true" /></button></div></nav> : null}
        {state.phase === 'ready' && eventType && state.data.items.length > 0 ? <p className="p4-caption">Showing {eventLabel(eventType).toLowerCase()} events. Filters are applied to backend audit records.</p> : null}
      </div></div>
  </section>
}
