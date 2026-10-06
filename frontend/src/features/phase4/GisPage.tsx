import { ArrowRight, Layers3, LocateFixed, MapPinned, RefreshCw, Search, ShieldAlert, ShieldCheck, Upload } from 'lucide-react'
import { Component, lazy, Suspense, useCallback, useMemo, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { phase4Api } from './api'
import { displayDate, gisHref, recordEvidenceHref, recordHref, reviewHref, titleCase } from './format'
import { sourcedLeafletRing } from './geometry'
import { isQaWorkspace } from '../../lib/workspace'
import type { GisParcel, Phase4PageProps } from './types'
import { usePhase4Data } from './usePhase4Data'
import { qualityScoreLabel } from '../live/format'
import { Modal } from '../../components/ui/Overlay'
import { Button } from '../../components/ui/Controls'
import { displayRoleName } from '../../lib/roles'
import './phase4.css'

const EMPTY_PARCELS: GisParcel[] = []
const ParcelMap = lazy(() => import('./ParcelMap').then((module) => ({ default: module.ParcelMap })))

class MapErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed ? <div className="p4-error" role="alert"><strong>Map could not load</strong><span>Your record list and source details remain available.</span><button type="button" onClick={() => window.location.reload()}>Reload map</button></div> : this.props.children
  }
}

function statusTone(parcel: GisParcel): string {
  const value = parcel.status.toLowerCase()
  if (value.includes('rejected') || value.includes('conflict')) return 'danger'
  if (value === 'verified') return 'success'
  return 'warning'
}

function options(items: GisParcel[], key: 'state' | 'district' | 'village'): string[] {
  return [...new Set(items.map((item) => item[key]).filter((value): value is string => Boolean(value)))].sort((a, b) => a.localeCompare(b))
}

function matches(parcel: GisParcel, search: string): boolean {
  const needle = search.trim().toLowerCase()
  return !needle || [parcel.surveyNumber, parcel.ownerName, parcel.recordNumber, parcel.recordId, parcel.village].some((value) => value?.toLowerCase().includes(needle))
}

function FilterSelect({ id, label, value, onChange, values }: { id: string; label: string; value: string; onChange: (value: string) => void; values: string[] }) {
  return <div className="p4-filter-field"><label className="p4-label" htmlFor={id}>{label}</label><select id={id} value={value} onChange={(event) => onChange(event.target.value)}><option value="">All {label.toLowerCase()}</option>{values.map((option) => <option key={option} value={option}>{['Validation', 'Record status'].includes(label) ? titleCase(option) : option}</option>)}</select></div>
}

export function GisPage({ token, user, recordId }: Phase4PageProps & { recordId?: string }) {
  const load = useCallback((signal: AbortSignal) => phase4Api.parcels(token, {}, signal), [token])
  const { state, retry } = usePhase4Data(`gis:${token}`, load)
  const [selectedId, setSelectedId] = useState<string | null>(() => recordId || new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('record'))
  const [focusId, setFocusId] = useState<string | null>(() => recordId || new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('record'))
  const [search, setSearch] = useState('')
  const [stateFilter, setStateFilter] = useState('')
  const [districtFilter, setDistrictFilter] = useState('')
  const [villageFilter, setVillageFilter] = useState('')
  const [validationFilter, setValidationFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [geometryFile, setGeometryFile] = useState<File | null>(null)
  const [sourceReference, setSourceReference] = useState('')
  const [importBusy, setImportBusy] = useState(false)
  const [importError, setImportError] = useState('')
  const [importSuccess, setImportSuccess] = useState('')
  const [replacement, setReplacement] = useState<{ parcel: GisParcel; file: File; sourceReference: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const trustedResponse = state.phase === 'ready' && state.data.synthetic === false
  const all = trustedResponse ? state.data.items : EMPTY_PARCELS
  const canImport = user.role === 'ADMIN' || user.role === 'REVENUE_OFFICER'
  const filtered = useMemo(() => all.filter((parcel) =>
    matches(parcel, search) && (!stateFilter || parcel.state === stateFilter) &&
    (!districtFilter || parcel.district === districtFilter) && (!villageFilter || parcel.village === villageFilter) &&
    (!validationFilter || parcel.validationStatus === validationFilter) && (!statusFilter || parcel.status === statusFilter)
  ), [all, search, stateFilter, districtFilter, villageFilter, validationFilter, statusFilter])
  const activeId = filtered.some((parcel) => parcel.recordId === selectedId) ? selectedId : selectedId ? null : filtered[0]?.recordId ?? null
  const selected = filtered.find((parcel) => parcel.recordId === activeId) ?? null
  const selectedHasGeometry = selected ? sourcedLeafletRing(selected) !== null : false
  const sourcedCount = filtered.filter((parcel) => sourcedLeafletRing(parcel) !== null).length
  const select = useCallback((id: string) => {
    setSelectedId(id)
    setFocusId(id)
    setImportError('')
    setImportSuccess('')
    setGeometryFile(null)
    setSourceReference('')
    setReplacement(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
    window.history.replaceState(null, '', gisHref(id))
  }, [])
  const verifiedCount = filtered.filter((item) => statusTone(item) === 'success').length
  const reviewCount = filtered.filter((item) => statusTone(item) === 'warning').length
  const conflictCount = filtered.filter((item) => statusTone(item) === 'danger').length

  async function importGeometry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selected || importBusy || !canImport) return
    if (!geometryFile || !/\.(geojson|json)$/i.test(geometryFile.name)) {
      setImportError('Choose a GeoJSON .geojson or .json file containing the parcel boundary.')
      return
    }
    if (sourceReference.trim().length < 4) {
      setImportError('Enter an identified source reference of at least four characters for this boundary.')
      return
    }
    setImportError('')
    if (selectedHasGeometry) {
      setReplacement({ parcel: selected, file: geometryFile, sourceReference: sourceReference.trim() })
      return
    }
    await saveGeometry(selected, geometryFile, sourceReference.trim(), false)
  }

  async function saveGeometry(parcel: GisParcel, file: File, reference: string, replacing: boolean) {
    if (importBusy || !canImport) return
    setImportBusy(true)
    setImportError('')
    setImportSuccess('')
    try {
      await phase4Api.importParcelGeometry(token, parcel.recordId, file, reference)
      setImportSuccess(`Parcel geometry ${replacing ? 'replaced' : 'imported'} for ${parcel.recordNumber || parcel.recordId}. The boundary, source file, and identified provenance were saved${replacing ? '; prior provenance remains recorded in the audit trail' : ''}.`)
      setReplacement(null)
      setGeometryFile(null)
      setSourceReference('')
      if (fileInputRef.current) fileInputRef.current.value = ''
      setFocusId(parcel.recordId)
      retry()
    } catch (error) {
      setImportError(error instanceof Error ? error.message : 'The geometry import failed.')
    } finally {
      setImportBusy(false)
    }
  }

  return <section className="p4-page p4-gis-page"><header className="p4-page-header"><div><span className="p4-eyebrow">Spatial workspace / linked records</span><h1>GIS intelligence</h1><p>Inspect land records and parcel boundaries imported from identified GeoJSON sources.</p></div><span className="p4-header-symbol"><MapPinned size={24} aria-hidden="true" /></span></header>
    <div className="p4-gis-disclaimer" role="note"><Layers3 size={18} aria-hidden="true" /><div><strong>Sourced parcel geometry</strong><span>{trustedResponse ? state.data.disclaimer : 'Only officer-imported WGS84 boundaries are displayed. Records without a sourced boundary remain visible in the list.'}</span></div></div>
    {isQaWorkspace ? <p className="p4-qa-notice" role="note">Synthetic/test data · This isolated QA map does not represent authoritative land records or parcel boundaries.</p> : null}
    {importSuccess ? <p className="p4-gis-import-success" role="status">{importSuccess}</p> : null}
    {trustedResponse ? <div className="p4-gis-stats"><span><i className="p4-legend-dot p4-legend-dot--success" /> {verifiedCount} officer-approved records</span><span><i className="p4-legend-dot p4-legend-dot--warning" /> {reviewCount} review / sent back</span><span><i className="p4-legend-dot p4-legend-dot--danger" /> {conflictCount} conflict / rejected</span><span>{sourcedCount} sourced boundaries · {filtered.length} visible records</span></div> : null}
    {state.phase === 'loading' ? <div className="p4-loading" role="status"><span className="p4-spinner" />Loading stored GIS records and boundary provenance…</div> : null}
    {state.phase === 'error' ? <div className="p4-error" role="alert"><strong>GIS data unavailable</strong><span>{state.error}</span><button type="button" onClick={retry}>Retry</button></div> : null}
    {state.phase === 'ready' && !trustedResponse ? <div className="p4-error" role="alert"><strong>Sourced GIS data unavailable</strong><span>The service returned a legacy synthetic dataset. No virtual parcel outlines will be shown.</span><button type="button" onClick={retry}>Retry</button></div> : null}
    {trustedResponse ? <div className="p4-gis-layout"><aside className="p4-gis-filters p4-card"><div className="p4-card-heading"><span className="p4-eyebrow">Find a record</span><h2>Filters</h2><button className="p4-icon-button" type="button" aria-label="Refresh GIS records" onClick={retry}><RefreshCw size={15} aria-hidden="true" /></button></div><div className="p4-gis-filter-body"><div className="p4-filter-field p4-filter-field--search"><label className="p4-label" htmlFor="p4-gis-search">Record search</label><div className="p4-search"><Search size={15} aria-hidden="true" /><input id="p4-gis-search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Survey, owner, ID…" /></div></div>
        <FilterSelect id="p4-gis-state" label="State" value={stateFilter} onChange={setStateFilter} values={options(all, 'state')} />
        <FilterSelect id="p4-gis-district" label="District" value={districtFilter} onChange={setDistrictFilter} values={options(all, 'district')} />
        <FilterSelect id="p4-gis-village" label="Village" value={villageFilter} onChange={setVillageFilter} values={options(all, 'village')} />
        <FilterSelect id="p4-gis-validation" label="Validation" value={validationFilter} onChange={setValidationFilter} values={[...new Set(all.map((item) => item.validationStatus))].sort()} />
        <FilterSelect id="p4-gis-status" label="Record status" value={statusFilter} onChange={setStatusFilter} values={[...new Set(all.map((item) => item.status))].sort()} />
        <div className="p4-gis-list" aria-label="GIS records">{filtered.map((parcel) => <button key={parcel.recordId} type="button" className={activeId === parcel.recordId ? 'p4-gis-list-item p4-gis-list-item--active' : 'p4-gis-list-item'} aria-pressed={activeId === parcel.recordId} onClick={() => select(parcel.recordId)}><span className={`p4-mini-dot p4-mini-dot--${statusTone(parcel)}`} /><span><strong>Survey {parcel.surveyNumber || '—'}</strong><small>{parcel.ownerName || 'Owner pending'} · {parcel.village || 'Village pending'}</small><small>{sourcedLeafletRing(parcel) ? 'Sourced boundary available' : 'Geometry unavailable'}</small></span><ArrowRight size={14} aria-hidden="true" /></button>)}{filtered.length === 0 ? <p className="p4-gis-empty-list">{all.length === 0 ? 'No GIS records yet. Process an operational document to create record metadata. A boundary requires an approved record and an identified GeoJSON source.' : 'No records match these filters. Adjust the search or location/status filters to inspect another record.'}</p> : null}</div></div></aside>
      <div className="p4-gis-map-card p4-card"><div className="p4-gis-map-head"><span><LocateFixed size={16} aria-hidden="true" /> Sourced WGS84 parcel boundaries</span><span>Select a marker or record</span></div><MapErrorBoundary><Suspense fallback={<div className="p4-map-loading" role="status"><span className="p4-spinner" />Loading interactive map…</div>}><ParcelMap parcels={filtered} selectedId={activeId} focusId={focusId} onSelect={select} role={user.role} /></Suspense></MapErrorBoundary><div className="p4-gis-map-foot"><span>Markers identify bounding-box centers · not surveyed points</span><span>{displayRoleName(user.role)} · {user.name}</span></div></div>
      <aside className="p4-gis-detail p4-card" key={activeId ?? 'unselected'}>
        <div className="p4-card-heading"><span className="p4-eyebrow">Selected record</span><h2>{selected ? `Survey ${selected.surveyNumber || '—'}` : 'No record selected'}</h2></div>
        {selected ? <>
          <span className={`p4-pill p4-pill--${statusTone(selected)}`}>{titleCase(selected.status)}</span>
          <div className="p4-gis-owner"><span>Record owner</span><strong>{selected.ownerName || 'Pending'}</strong></div>
          <dl className="p4-gis-details">
            <div><dt>Record</dt><dd>{selected.recordNumber || selected.recordId}</dd></div>
            <div><dt>Recorded area</dt><dd>{selected.area == null ? '—' : `${selected.area} ${selected.areaUnit || ''}`}</dd></div>
            <div><dt>Village</dt><dd>{selected.village || '—'}</dd></div>
            <div><dt>District / State</dt><dd>{selected.district || '—'} / {selected.state || '—'}</dd></div>
            <div><dt>Validation</dt><dd>{titleCase(selected.validationStatus)}</dd></div>
            <div><dt>Quality score</dt><dd>{selected.qualityScore == null ? '—' : `${qualityScoreLabel(selected.qualityScore)} / 100`}</dd></div>
            <div><dt>Boundary</dt><dd>{selectedHasGeometry ? 'Sourced WGS84 geometry' : 'Parcel geometry unavailable'}</dd></div>
            {selectedHasGeometry ? <>
              <div><dt>Source reference</dt><dd>{selected.geometryReference || '—'}</dd></div>
              <div><dt>Source file</dt><dd>{selected.geometryFileName || '—'}</dd></div>
              <div><dt>Recorded</dt><dd>{selected.geometryRecordedAt ? displayDate(selected.geometryRecordedAt) : '—'}</dd></div>
              <div><dt>Recorded by</dt><dd>{selected.geometryRecordedBy || '—'}</dd></div>
              <div><dt>Source SHA-256</dt><dd>{selected.geometrySha256 || '—'}</dd></div>
            </> : null}
            <div><dt>GIS indexed</dt><dd>{selectedHasGeometry && selected.indexedAt ? displayDate(selected.indexedAt) : '—'}</dd></div>
          </dl>
          <div className="p4-gis-source"><ShieldAlert size={16} aria-hidden="true" /><span>{selectedHasGeometry ? 'Boundary imported from the named GeoJSON source. Officer verification of the land record is separate from boundary provenance.' : 'Parcel geometry unavailable. No parcel boundary is inferred from the record number, owner, survey number, or address.'}</span></div>
          {canImport && selected.status !== 'verified' ? <p className="p4-gis-import-note">A Revenue Officer or Administrator must make the final approval before this record's sourced boundary can be imported.</p> : null}
          {canImport && selected.status === 'verified' ? <form className="p4-gis-import" onSubmit={(event) => void importGeometry(event)}>
            <h3><Upload size={15} aria-hidden="true" />{selectedHasGeometry ? 'Replace parcel geometry' : 'Import parcel geometry'}</h3>
            <p>Use a GeoJSON Polygon from an identified source for this approved record. The service validates its WGS84 coordinates.</p>
            <label htmlFor="p4-gis-source-reference">Source reference</label>
            <input id="p4-gis-source-reference" value={sourceReference} onChange={(event) => setSourceReference(event.target.value)} minLength={4} maxLength={200} required disabled={importBusy} placeholder="Identified source ID · minimum 4 characters" />
            <label htmlFor="p4-gis-geometry-file">GeoJSON boundary file</label>
            <input ref={fileInputRef} id="p4-gis-geometry-file" type="file" accept=".geojson,.json,application/geo+json,application/json" aria-label="Choose GeoJSON parcel boundary" onChange={(event) => setGeometryFile(event.target.files?.[0] || null)} disabled={importBusy} />
            {importError ? <p className="p4-gis-import-error" role="alert">{importError}</p> : null}
            <button type="submit" disabled={importBusy} aria-busy={importBusy}>{importBusy ? <><span className="p4-spinner" />Saving parcel geometry…</> : selectedHasGeometry ? 'Replace parcel geometry' : 'Import parcel geometry'}</button>
          </form> : null}
          <div className="p4-gis-record-links"><a className="p4-primary-link" href={recordHref(selected.recordId)}>View record <ArrowRight size={15} aria-hidden="true" /></a><a className="p4-text-link" href={reviewHref(selected.recordId)}>{user.role === 'AUDITOR' ? 'View review' : 'Review record'} <ArrowRight size={14} aria-hidden="true" /></a><a className="p4-text-link" href={recordEvidenceHref(selected.recordId)}>View evidence <ArrowRight size={14} aria-hidden="true" /></a></div>
        </> : <div className="p4-empty p4-gis-empty"><MapPinned size={24} aria-hidden="true" /><strong>{selectedId ? 'Selected record unavailable in this view' : 'No record selected'}</strong><span>Adjust filters or select a record from the list.</span></div>}
      </aside>
    </div> : null}
    <Modal open={replacement !== null} onClose={() => { if (!importBusy) setReplacement(null) }} title="Confirm geometry replacement" description={replacement ? `Record ${replacement.parcel.recordNumber || replacement.parcel.recordId}` : undefined} size="sm" footer={<><Button variant="secondary" disabled={importBusy} onClick={() => setReplacement(null)}>Cancel</Button><Button loading={importBusy} onClick={() => { if (replacement) void saveGeometry(replacement.parcel, replacement.file, replacement.sourceReference, true) }}>{importBusy ? 'Saving replacement…' : 'Confirm replacement'}</Button></>}>
      {replacement ? <div className="p4-geometry-confirm"><p>This replaces the current parcel boundary. The imported source file and provenance will be saved; prior provenance remains recorded in the audit trail. The land-record final decision stays unchanged.</p><dl><div><dt>Current source</dt><dd>{replacement.parcel.geometryReference || 'Not recorded'}</dd></div><div><dt>New source</dt><dd>{replacement.sourceReference}</dd></div><div><dt>New file</dt><dd>{replacement.file.name}</dd></div></dl><p>Coordinate validation does not certify a government boundary or surveyed location.</p>{importError ? <p className="p4-gis-import-error" role="alert">{importError}</p> : null}</div> : null}
    </Modal>
    <p className="p4-gis-footer"><ShieldCheck size={14} aria-hidden="true" /> The map shows only officer-imported boundaries with an identified source. Land-record approval remains a separate human decision.</p>
  </section>
}
