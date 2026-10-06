import { ArrowRight, FileText, Hash, MapPin, RefreshCw, Search, X } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { ApiRequestError } from '../api/client'
import { reportUnauthorizedSession } from '../features/auth/session'
import { navigationItems, routeAvailableForRole, routeHref } from './navigation'
import { useDialogFocus } from './useDialogFocus'

interface GlobalSearchProps {
  onClose: () => void
  role: string
  token: string
}

interface SearchHit {
  id: string
  title: string
  subtitle: string
  href: string
  recordNumber?: string | null
  ownerName?: string | null
  surveyNumber?: string | null
  khataNumber?: string | null
  village?: string | null
  district?: string | null
  fileName?: string | null
  status?: string | null
}

interface SearchResponse {
  query: string
  total: number
  records: SearchHit[]
  documents: SearchHit[]
  surveys: SearchHit[]
}

type SearchState = { phase: 'idle' } | { phase: 'loading'; query: string } | { phase: 'ready'; query: string; data: SearchResponse } | { phase: 'error'; query: string; message: string }
const apiBase = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

async function searchData(query: string, token: string, signal: AbortSignal): Promise<SearchResponse> {
  let response: Response
  try {
    response = await fetch(`${apiBase}/search?q=${encodeURIComponent(query)}`, { signal, headers: { Accept: 'application/json', Authorization: `Bearer ${token}` } })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('Search could not reach the backend. Check the connection and retry.')
  }
  if (!response.ok) {
    if (response.status === 401) reportUnauthorizedSession()
    throw new ApiRequestError(`Search returned HTTP ${response.status}.`, response.status)
  }
  const data = await response.json() as SearchResponse
  if (!Array.isArray(data.records) || !Array.isArray(data.documents) || !Array.isArray(data.surveys)) throw new ApiRequestError('Search returned an unreadable result.')
  return data
}

function ResultGroup({ title, items, icon: Icon, onClose }: { title: string; items: SearchHit[]; icon: typeof FileText; onClose: () => void }) {
  if (!items.length) return null
  return <section aria-label={title}>
    <h2 className="bd-command-caption">{title} <span className="font-medium tabular-nums">· {items.length}</span></h2>
    <ul>{items.map((item) => <li key={item.id}><a href={item.href.startsWith('#/') ? item.href : '#/records'} onClick={onClose}><span className="bd-command-result-icon"><Icon size={17} aria-hidden="true" /></span><span><strong>{item.title}</strong><small style={{ whiteSpace: 'normal', overflow: 'visible', lineHeight: 1.4 }}>{item.khataNumber ? `Khata ${item.khataNumber} · ` : ''}{item.subtitle} · ID {item.id.slice(0, 8)}</small></span><ArrowRight size={16} aria-hidden="true" /></a></li>)}</ul>
  </section>
}

export function GlobalSearch({ onClose, role, token }: GlobalSearchProps) {
  const [query, setQuery] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [state, setState] = useState<SearchState>({ phase: 'idle' })
  const dialogRef = useDialogFocus<HTMLDivElement>(true, onClose)
  const normalized = query.trim()
  const routeResults = useMemo(() => navigationItems.filter((item) => item.phase === 'available' && routeAvailableForRole(item.id, role) && (!normalized || `${item.label} ${item.description}`.toLocaleLowerCase().includes(normalized.toLocaleLowerCase()))), [normalized, role])

  useEffect(() => {
    if (normalized.length < 2) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void searchData(normalized, token, controller.signal).then(
        (data) => { if (!controller.signal.aborted) setState({ phase: 'ready', query: normalized, data }) },
        (error: unknown) => { if (!controller.signal.aborted) setState({ phase: 'error', query: normalized, message: error instanceof Error ? error.message : 'Search failed.' }) },
      )
    }, 250)
    return () => { window.clearTimeout(timer); controller.abort() }
  }, [normalized, token, retryCount])

  const effectiveState: SearchState = normalized.length < 2 ? { phase: 'idle' } : state.phase === 'idle' || state.query !== normalized ? { phase: 'loading', query: normalized } : state
  const data = effectiveState.phase === 'ready' ? effectiveState.data : null
  const dataCount = data ? data.records.length + data.documents.length + data.surveys.length : 0

  return createPortal(
    <div className="bd-modal-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <div ref={dialogRef} className="bd-command-dialog" role="dialog" aria-modal="true" aria-label="Search records, documents, surveys, and pages" tabIndex={-1}>
        <div className="bd-command-input-row"><Search size={19} aria-hidden="true" /><input value={query} onChange={(event) => { setQuery(event.target.value); setState({ phase: 'idle' }) }} placeholder="Record ID, owner, survey, khata, village, district…" aria-label="Search records, documents, surveys, and pages" maxLength={100} /><button type="button" onClick={onClose} aria-label="Close search"><X size={18} aria-hidden="true" /></button></div>
        <div className="bd-command-results" aria-live="polite">
          {normalized.length === 1 && <p className="bd-command-empty">Enter at least two characters to search the prototype register.</p>}
          {normalized.length >= 2 && <><p className="bd-command-caption">Search the prototype register</p>{effectiveState.phase === 'loading' && <p className="bd-command-empty" role="status">Searching records and documents…</p>}{effectiveState.phase === 'error' && <div className="bd-command-empty" role="alert"><p>{effectiveState.message}</p><button type="button" onClick={() => setRetryCount((count) => count + 1)} className="mt-2 inline-flex items-center gap-1 font-semibold text-[var(--bd-accent)]"><RefreshCw size={13} aria-hidden="true" />Retry search</button></div>}{data && <><ResultGroup title="Records" items={data.records} icon={FileText} onClose={onClose} /><ResultGroup title="Documents" items={data.documents} icon={FileText} onClose={onClose} /><ResultGroup title="Survey references" items={data.surveys} icon={MapPin} onClose={onClose} />{dataCount === 0 && routeResults.length === 0 && <p className="bd-command-empty">No matches for “{normalized}”. Try a record number, owner, survey, khata, village, or document name.</p>}</>}</>}
          {routeResults.length > 0 && <section aria-label="Workspace pages"><h2 className="bd-command-caption">{normalized ? 'Workspace pages' : 'Navigate to'}</h2><ul>{routeResults.map((item) => { const Icon = item.icon; return <li key={item.id}><a href={routeHref(item.id)} onClick={onClose}><span className="bd-command-result-icon"><Icon size={17} aria-hidden="true" /></span><span><strong>{item.label}</strong><small>{item.description}</small></span><ArrowRight size={16} aria-hidden="true" /></a></li> })}</ul></section>}
          {!normalized && <p className="bd-command-empty"><Hash size={13} className="mr-1 inline" aria-hidden="true" />Search persisted prototype records and documents, or choose a workspace page.</p>}
        </div>
        <div className="bd-command-footer"><span>{normalized && data ? `${data.total} matching items in this local prototype` : 'Record and document search · prototype data'}</span><span><kbd>Esc</kbd> to close</span></div>
      </div>
    </div>, document.body
  )
}
