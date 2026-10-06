import { ArrowRight, Archive, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { phase4Api } from './api'
import { displayDate, recordHref, titleCase } from './format'
import type { Phase4PageProps, RecordListItem } from './types'
import { usePhase4Data } from './usePhase4Data'
import { qualityScoreLabel } from '../live/format'
import './phase4.css'

function itemId(item: RecordListItem): string { return String(item.recordId || item.id || '') }
function itemStatus(item: RecordListItem): string { return String(item.recordStatus || item.validationStatus || '').toLowerCase() }
function statusLabel(status: string): string { return status === 'approved' ? 'Officer verified' : titleCase(status) }
function statusTone(status: string): string { return status === 'verified' ? 'success' : ['rejected', 'conflict'].includes(status) ? 'danger' : 'warning' }

export function RecordsPage({ token, user }: Phase4PageProps) {
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('all')
  const load = useCallback((signal: AbortSignal) => phase4Api.records(token, { limit: 100 }, signal), [token])
  const { state, retry } = usePhase4Data(`records:${token}`, load)
  const filtered = useMemo(() => state.phase !== 'ready' ? [] : state.data.items.filter((item) => {
    const needle = search.trim().toLowerCase()
    const matchesText = !needle || [item.recordNumber, item.ownerName, item.surveyNumber, item.village, item.district, itemId(item)].some((value) => value?.toLowerCase().includes(needle))
    const actualStatus = itemStatus(item)
    return matchesText && (status === 'all' || actualStatus === status)
  }), [search, state, status])
  const statusOptions = state.phase === 'ready' ? [...new Set(state.data.items.map(itemStatus).filter(Boolean))].sort() : []

  return <section className="p4-page p4-records-page"><header className="p4-page-header"><div><span className="p4-eyebrow">Registry / traceable records</span><h1>Land records</h1><p>Inspect structured records, officer review outcomes, audit history, and GIS links.</p></div><span className="p4-header-symbol"><Archive size={24} aria-hidden="true" /></span></header>
    <div className="p4-filter-bar p4-card"><div className="p4-search"><Search size={16} aria-hidden="true" /><input aria-label="Search records" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Owner, survey, village, record ID…" /></div><label>Record status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="all">All statuses</option>{statusOptions.map((value) => <option key={value} value={value}>{statusLabel(value)}</option>)}</select></label><button type="button" className="p4-icon-button" aria-label="Refresh records" onClick={retry}><RefreshCw size={16} aria-hidden="true" /></button></div>
    <div className="p4-section-heading"><div><span className="p4-eyebrow">Record registry</span><h2>{state.phase === 'ready' ? `${filtered.length} record${filtered.length === 1 ? '' : 's'}` : 'Loading records'}</h2></div><span className="p4-small-note"><ShieldCheck size={14} aria-hidden="true" /> Viewed as {user.name}</span></div>
    {state.phase === 'loading' ? <div className="p4-loading" role="status"><span className="p4-spinner" />Loading records…</div> : null}
    {state.phase === 'error' ? <div className="p4-error" role="alert"><strong>Records unavailable</strong><span>{state.error}</span><button type="button" onClick={retry}>Retry</button></div> : null}
    {state.phase === 'ready' && filtered.length === 0 ? <div className="p4-empty"><Archive size={25} aria-hidden="true" /><strong>{state.data.items.length ? 'No matching records' : 'No records yet'}</strong><span>{state.data.items.length ? 'Try another search or status.' : 'Records appear here after document processing and officer review.'}</span></div> : null}
    {state.phase === 'ready' && filtered.length ? <div className="p4-records-grid">{filtered.map((item) => <a key={itemId(item)} className="p4-record-card p4-card" href={recordHref(itemId(item))}><div><span className="p4-eyebrow">{item.recordNumber || itemId(item)}</span><span className={`p4-pill p4-pill--${statusTone(itemStatus(item))}`}>{statusLabel(itemStatus(item))}</span></div><h3>{item.ownerName || 'Owner pending'}</h3><p>Survey {item.surveyNumber || '—'} · {item.village || 'Village pending'}, {item.district || 'District pending'}</p><div><span>{item.qualityScore == null ? 'Score pending' : `Quality ${qualityScoreLabel(item.qualityScore)} / 100`}</span><span>{item.updatedAt ? displayDate(item.updatedAt) : 'Open details'}</span><ArrowRight size={16} aria-hidden="true" /></div></a>)}</div> : null}
  </section>
}
