import { useEffect, useMemo, useState } from 'react'
import { AlertCircle, ArrowRight, CheckCircle2, ChevronDown, Clock3, FileSearch2, Filter, RefreshCw, Search, ShieldAlert, UserRound } from 'lucide-react'
import { listReviews } from './api'
import { qualityScoreLabel } from '../live/format'
import { priorityLabel, reviewDate, reviewStatusLabel } from './format'
import { QUEUE_FILTERS, type QueueFilter, type QueueSort, type ReviewCaseSummary, type ReviewUser } from './types'
import './review.css'
import { displayRoleName } from '../../lib/roles'

type Props = { token: string; user: ReviewUser }

function PriorityTag({ item }: { item: ReviewCaseSummary }) {
  return <span className={`rv-priority rv-priority--${item.priority.toLowerCase()}`}><span />{priorityLabel(item.priority)} priority</span>
}

function QueueCard({ item }: { item: ReviewCaseSummary }) {
  return <a className="rv-queue-card" href={`#/review/${encodeURIComponent(item.recordId)}`} aria-label={`Open ${item.recordNumber || item.recordId} for review`}>
    <div className="rv-queue-card__lead">
      <div className="rv-queue-card__identity"><span className="rv-queue-card__record">{item.recordNumber || item.recordId}</span><strong>{item.ownerName || 'Owner not detected'}</strong><small>Survey {item.surveyNumber || 'not detected'} · {item.documentName}</small><small className="rv-record-uuid" title={item.recordId}>ID {item.recordId}</small></div>
      <div className="rv-score" aria-label={`Quality score ${qualityScoreLabel(item.qualityScore)} out of 100`}><strong>{qualityScoreLabel(item.qualityScore)}</strong><span>/100</span></div>
    </div>
    <div className="rv-queue-card__meta"><PriorityTag item={item} /><span className="rv-queue-card__status">{reviewStatusLabel(item.status)} · {item.validationStatus.replace(/_/g, ' ')}</span></div>
    <p className="rv-queue-card__conflict">{item.primaryConflict || 'No primary conflict recorded'}</p>
    <div className="rv-queue-card__reasons">{item.priorityReasons.slice(0, 2).map((reason) => <span key={reason}>{reason}</span>)}</div>
    <div className="rv-queue-card__foot"><span><Clock3 size={13} />{reviewDate(item.submittedAt)}</span><span><UserRound size={13} />{item.assignedOfficer?.name || 'Unassigned'}</span><ArrowRight size={16} /></div>
  </a>
}

export function ReviewQueuePage({ token, user }: Props) {
  const [filter, setFilter] = useState<QueueFilter>('all')
  const [search, setSearch] = useState('')
  const [settledSearch, setSettledSearch] = useState('')
  const [sort, setSort] = useState<QueueSort>('submitted_at')
  const [direction, setDirection] = useState<'asc' | 'desc'>('desc')
  const [items, setItems] = useState<ReviewCaseSummary[]>([])
  const [total, setTotal] = useState(0)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const [loadedKey, setLoadedKey] = useState('')
  const [error, setError] = useState('')
  const [revision, setRevision] = useState(0)
  const requestKey = JSON.stringify([token, filter, settledSearch, sort, direction, revision])
  const viewState = loadedKey === requestKey ? state : 'loading'

  useEffect(() => {
    const timeout = window.setTimeout(() => setSettledSearch(search.trim()), 250)
    return () => window.clearTimeout(timeout)
  }, [search])

  useEffect(() => {
    const controller = new AbortController()
    listReviews(token, { filter, search: settledSearch, sort, direction, limit: 100 }, controller.signal)
      .then((result) => { setItems(result.items); setTotal(result.total); setState('ready'); setError(''); setLoadedKey(requestKey) })
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === 'AbortError') return
        setState('error')
        setError(reason instanceof Error ? reason.message : 'Review cases could not be loaded.')
        setLoadedKey(requestKey)
      })
    return () => controller.abort()
  }, [token, filter, settledSearch, sort, direction, revision, requestKey])

  const counts = useMemo(() => ({ high: items.filter((item) => item.priority === 'high').length, unassigned: items.filter((item) => !item.assignedOfficer).length }), [items])

  return <section className="rv-page" aria-label="Review queue">
    <div className="rv-breadcrumb"><span>SIH 2026 / SIH26018</span><span className="rv-breadcrumb__slash">/</span><span>Human review</span></div>
    <header className="rv-page-header"><div><span className="rv-eyebrow">Human review · evidence first</span><h1>Review queue</h1><p>Resolve flagged land records with original source evidence, explicit field decisions, and a recorded outcome.</p></div><a className="rv-header-link" href="#/documents">{['ADMIN', 'REVENUE_OFFICER'].includes(user.role) ? 'Upload a record' : 'Inspect documents'} <ArrowRight size={15} /></a></header>
    <div className="rv-auth-note"><ShieldAlert size={17} aria-hidden="true" /><span><strong>Authenticated review.</strong> Signed in as {user.name} ({displayRoleName(user.role)}). Final verification is a human decision; extracted fields are supporting evidence.</span></div>

    <div className="rv-queue-stats" aria-label="Queue view summary">
      <div><span className="rv-stat-icon rv-stat-icon--green"><FileSearch2 size={18} /></span><span>Cases in current view</span><strong>{viewState === 'ready' ? total : '—'}</strong><small>Matching the current filters</small></div>
      <div><span className="rv-stat-icon rv-stat-icon--amber"><ShieldAlert size={18} /></span><span>High priority</span><strong>{viewState === 'ready' ? counts.high : '—'}</strong><small>Visible cases requiring attention</small></div>
      <div><span className="rv-stat-icon rv-stat-icon--blue"><UserRound size={18} /></span><span>Unassigned</span><strong>{viewState === 'ready' ? counts.unassigned : '—'}</strong><small>Visible cases without an officer</small></div>
    </div>

    <div className="rv-queue-surface">
      <div className="rv-queue-toolbar"><div className="rv-queue-toolbar__title"><span className="rv-eyebrow">Work to verify</span><h2>Cases requiring review</h2><p>Priority is rule based and each reason is shown on the case.</p></div><button type="button" className="rv-icon-button" title="Refresh queue" aria-label="Refresh queue" onClick={() => setRevision((value) => value + 1)}><RefreshCw size={16} /></button></div>
      <div className="rv-filter-area"><div className="rv-search"><Search size={16} aria-hidden="true" /><input aria-label="Search review queue" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search record, owner, survey or document" /></div><div className="rv-sort"><label htmlFor="rv-sort">Sort</label><span><select id="rv-sort" value={`${sort}:${direction}`} onChange={(event) => { const [nextSort, nextDirection] = event.target.value.split(':') as [QueueSort, 'asc' | 'desc']; setSort(nextSort); setDirection(nextDirection) }}><option value="submitted_at:desc">Newest submitted</option><option value="submitted_at:asc">Oldest submitted</option><option value="priority:desc">Highest priority</option><option value="quality_score:asc">Lowest score</option><option value="quality_score:desc">Highest score</option></select><ChevronDown size={14} /></span></div></div>
      <div className="rv-filters" aria-label="Review queue filters"><Filter size={15} aria-hidden="true" />{QUEUE_FILTERS.map((entry) => <button key={entry.value} type="button" className={filter === entry.value ? 'rv-filter rv-filter--active' : 'rv-filter'} aria-pressed={filter === entry.value} onClick={() => setFilter(entry.value)}>{entry.label}</button>)}</div>

      {viewState === 'loading' ? <div className="rv-queue-state" role="status"><span className="rv-spinner" />Loading review cases…</div> : null}
      {viewState === 'error' ? <div className="rv-queue-state rv-queue-state--error" role="alert"><AlertCircle size={19} /><span>{error}</span><button type="button" onClick={() => setRevision((value) => value + 1)}>Retry</button></div> : null}
      {viewState === 'ready' && items.length === 0 ? <div className="rv-queue-empty"><CheckCircle2 size={28} /><h3>No cases match this view</h3><p>{filter !== 'all' || settledSearch ? 'Change the filters or search to see other cases.' : 'Processed records awaiting human review appear here. A Revenue Officer or Administrator uploads and processes the original source.'}</p><a href="#/documents">Open document workspace <ArrowRight size={13} /></a></div> : null}
      {viewState === 'ready' && items.length > 0 ? <><div className="rv-queue-head" aria-hidden="true"><span>Record & quality</span><span>Priority / status</span><span>Primary conflict</span><span>Reasons</span><span>Submitted / assigned</span></div><div className="rv-queue-list">{items.map((item) => <QueueCard key={item.recordId} item={item} />)}</div><div className="rv-queue-footer">Showing {items.length} of {total} matching cases{total > items.length ? ' · refine the filters to narrow the queue' : ''}</div></> : null}
    </div>
  </section>
}
