import { ArrowLeft, ArrowRight, BookOpenCheck, ClipboardCheck, FileSearch, FileText, History, MapPinned, RefreshCw, ShieldCheck, UserRound, Waves } from 'lucide-react'
import { useCallback } from 'react'
import { phase4Api } from './api'
import { AuditTimeline } from './AuditTimeline'
import { auditHref, displayDate, displayValue, fieldLabel, gisHref, recordHref, reviewHref, titleCase } from './format'
import { sourcedLeafletRing } from './geometry'
import { isQaWorkspace } from '../../lib/workspace'
import type { CanonicalRecord, Phase4PageProps, RecordDetailResponse } from './types'
import { usePhase4Data } from './usePhase4Data'
import { qualityScoreLabel } from '../live/format'
import { displayRoleName } from '../../lib/roles'
import './phase4.css'

type Section = 'overview' | 'ownership' | 'land' | 'registration' | 'validation' | 'evidence' | 'review' | 'audit' | 'gis'
const sections: { id: Section; label: string }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'ownership', label: 'Ownership' }, { id: 'land', label: 'Land details' },
  { id: 'registration', label: 'Registration' }, { id: 'validation', label: 'Validation' },
  { id: 'evidence', label: 'Evidence' }, { id: 'review', label: 'Review history' },
  { id: 'audit', label: 'Audit trail' }, { id: 'gis', label: 'GIS' },
]

function object(value: unknown): Record<string, unknown> { return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {} }
function text(value: unknown): string | null { return typeof value === 'string' && value.trim() ? value : null }
function number(value: unknown): number | null { return typeof value === 'number' && Number.isFinite(value) ? value : null }
function finalDecision(review: Record<string, unknown>): string {
  return review.status === 'approved' ? 'Approve' : review.status === 'rejected' ? 'Reject' : review.status === 'sent_back' ? 'Send back' : 'Pending'
}
function decisionRole(detail: RecordDetailResponse): string | null {
  const review = object(detail.review)
  const eventType = review.status === 'approved' ? 'RECORD_APPROVED' : review.status === 'rejected' ? 'RECORD_REJECTED' : review.status === 'sent_back' ? 'RECORD_SENT_BACK' : null
  const event = detail.auditEvents?.find((item) => item.eventType === eventType && item.actorId === review.decidedBy && item.metadata?.reviewCaseId === review.id)
  return text(event?.actorRole)
}

function DetailGrid({ values }: { values: [string, unknown][] }) {
  return <dl className="p4-detail-grid">{values.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{displayValue(value)}</dd></div>)}</dl>
}

function RecordBody({ detail, section }: { detail: RecordDetailResponse; section: Section }) {
  const record = detail.record
  const review = object(detail.review)
  const ownership = object(record.ownershipDetails)
  const registration = object(record.registrationInformation)
  const validation = object(review.validation ?? record.validation)
  const scoreBreakdown = object(review.scoreBreakdown)
  const document = object(record.sourceDocument)
  const provenance = object(record.provenance)
  const fieldReviews = Array.isArray(review.fieldReviews) ? review.fieldReviews : []
  const recommendation = object(review.recommendation)
  const resolutions = Array.isArray(review.issueResolutions) ? review.issueResolutions : []
  const finalRole = decisionRole(detail)

  if (section === 'overview') return <div className="p4-record-columns"><div className="p4-card p4-record-section"><h2><FileText size={18} aria-hidden="true" /> Record overview</h2><DetailGrid values={[
    ['Record number', record.recordNumber], ['Owner', record.ownerName], ['Survey number', record.surveyNumber],
    ['Source document', document.fileName], ['Document language', document.language], ['Record validation status', text(record.validationStatus) ? titleCase(String(record.validationStatus)) : null],
  ]} />{text(document.documentId) ? <a className="p4-text-link" href={`#/documents?id=${encodeURIComponent(document.documentId as string)}`}>Inspect original source <ArrowRight size={14} aria-hidden="true" /></a> : null}</div><div className="p4-card p4-record-section"><h2><ShieldCheck size={18} aria-hidden="true" /> Review and final-decision context</h2><p className="p4-section-copy">Text extraction and rule-based validation support human review. Corrections and final decisions remain linked to the source and audit trail.</p><DetailGrid values={[
    ['Review status', text(review.status ?? review.reviewStatus) ? titleCase(String(review.status ?? review.reviewStatus)) : 'Pending'],
    ['Assigned officer', review.assignedOfficerName ?? review.assignedOfficerId],
    ['Final decision', finalDecision(review)], ['Final decision by', review.decidedByName ?? review.decidedBy],
    ['Final actor role', finalRole ? displayRoleName(finalRole) : null],
    ['Final decision time', review.decidedAt ? displayDate(String(review.decidedAt)) : null],
    ['Processing quality score', review.qualityScore ?? scoreBreakdown.qualityScore ?? validation.qualityScore],
  ]} /></div></div>

  if (section === 'ownership') return <div className="p4-card p4-record-section"><h2><UserRound size={18} aria-hidden="true" /> Ownership information</h2><DetailGrid values={[
    ['Owner name', record.ownerName], ['Father or guardian', record.fatherOrGuardianName], ['Owners', ownership.owners],
    ['Share fraction', ownership.shareFraction], ['Tenure type', ownership.tenureType], ['Notes', ownership.notes],
  ]} /><p className="p4-section-note">These are transcribed source details. Approval in this workspace records a human review decision; it does not determine legal ownership.</p></div>

  if (section === 'land') return <div className="p4-card p4-record-section"><h2><Waves size={18} aria-hidden="true" /> Land and location</h2><DetailGrid values={[
    ['Survey number', record.surveyNumber], ['Khasra number', record.khasraNumber], ['Khata number', record.khataNumber],
    ['Area', record.area], ['Area unit', record.areaUnit], ['Classification', record.landClassification],
    ['Village', record.village], ['Mandal or tehsil', record.mandalOrTehsil], ['District', record.district], ['State', record.state],
  ]} /></div>

  if (section === 'registration') return <div className="p4-record-columns"><div className="p4-card p4-record-section"><h2><BookOpenCheck size={18} aria-hidden="true" /> Registration</h2><DetailGrid values={[
    ['Registration number', registration.registrationNumber], ['Registration date', registration.registrationDate],
    ['Sub-registrar office', registration.subRegistrarOffice], ['Deed type', registration.deedType],
  ]} /></div><div className="p4-card p4-record-section"><h2><History size={18} aria-hidden="true" /> Mutation records</h2>{Array.isArray(record.mutationRecords) && record.mutationRecords.length ? <div className="p4-detail-list">{record.mutationRecords.map((mutation, index) => <div key={index}><DetailGrid values={Object.entries(object(mutation)).map(([key, value]) => [fieldLabel(key), value])} /></div>)}</div> : <p className="p4-section-copy">No mutation records were extracted from this source.</p>}</div></div>

  if (section === 'validation') return <div className="p4-card p4-record-section"><h2><ClipboardCheck size={18} aria-hidden="true" /> Validation findings and processing score</h2><p className="p4-section-copy">These are the original processing findings. Subsequent human resolutions appear in Review history.</p>{Object.keys(validation).length ? <><div className="p4-score-strip">{(['fieldScore', 'recordScore', 'crossSystemScore', 'qualityScore'] as const).map((key) => <div key={key}><span>{fieldLabel(key)}</span><strong>{number(validation[key])?.toFixed(1) ?? '—'}</strong></div>)}</div>{Array.isArray(validation.issues) && validation.issues.length ? <div className="p4-issue-list">{validation.issues.map((issue, index) => { const item = object(issue); return <div key={index}><span className={`p4-mini-dot ${item.severity === 'error' ? 'p4-mini-dot--danger' : ''}`} /><span><strong>{displayValue(item.message)}</strong><small>{displayValue(item.level)} · {displayValue(item.fieldName)}</small></span></div> })}</div> : <p className="p4-section-copy">No validation findings were recorded by processing. See Review history for the recorded human decision.</p>}</> : <p className="p4-section-copy">Validation findings become available after document processing.</p>}</div>

  if (section === 'evidence') return <div className="p4-card p4-record-section"><h2><FileSearch size={18} aria-hidden="true" /> Evidence · original source</h2><p className="p4-section-copy">Evidence below retains extracted source text. Human-reviewed values and their reasons appear separately in Review history.</p>{text(document.documentId) ? <a className="p4-text-link p4-record-source-link" href={`#/documents?id=${encodeURIComponent(document.documentId as string)}`}>Inspect original source pages <ArrowRight size={14} aria-hidden="true" /></a> : null}{Object.keys(provenance).length ? <div className="p4-evidence-list">{Object.entries(provenance).map(([field, raw]) => { const evidence = object(raw); const confidence = number(evidence.confidence); return <div key={field}><strong>{fieldLabel(field)}</strong><span>{displayValue(evidence.extractedText)}</span><small>Page {displayValue(evidence.sourcePage)} · Recognition confidence {confidence === null ? 'unmeasured' : `${Math.round(confidence * 100)}%`}</small></div> })}</div> : <p className="p4-section-copy">No field-level source evidence was stored for this record. Inspect the original source document when available.</p>}</div>

  if (section === 'review') return <div className="p4-card p4-record-section"><h2><UserRound size={18} aria-hidden="true" /> Review history</h2><p className="p4-section-copy">This shows the latest review attempt and its persisted field decisions, finding resolutions, recommendation, and final decision.</p><h3 className="p4-record-subheading">Final decision</h3><DetailGrid values={[
    ['Review status', text(review.status ?? review.reviewStatus) ? titleCase(String(review.status ?? review.reviewStatus)) : null], ['Assigned officer', review.assignedOfficerName ?? review.assignedOfficerId],
    ['Final decision', finalDecision(review)], ['Final decision by', review.decidedByName ?? review.decidedBy],
    ['Actor role', finalRole ? displayRoleName(finalRole) : null], ['Decision reason', review.decisionReason],
    ['Decision time', review.decidedAt ? displayDate(String(review.decidedAt), { dateStyle: 'medium', timeStyle: 'long' }) : null],
  ]} /><div className="p4-record-recommendation"><h3>{recommendation.reviewerRole === 'VERIFIER' ? 'Verifier recommendation' : 'Recommendation'} · advisory</h3>{Object.keys(recommendation).length ? <><strong>{text(recommendation.value) ? titleCase(String(recommendation.value)) : 'Outcome not recorded'}</strong><p>Reason: {text(recommendation.reason) ?? 'No reason recorded.'}</p><small>{text(recommendation.reviewerRole) ? displayRoleName(String(recommendation.reviewerRole)) : 'Role not recorded'} · Reviewer ID {displayValue(recommendation.reviewerId)} · {text(recommendation.at) ? displayDate(String(recommendation.at)) : 'Time not recorded'}</small><p>A recommendation is not a final decision.</p></> : <p>No recommendation was recorded for this attempt. A recommendation and the authorized final decision are separate actions.</p>}</div>{fieldReviews.length ? <div className="p4-review-changes"><h3>Field decisions · extracted and human-reviewed values</h3>{fieldReviews.map((raw, index) => { const field = object(raw); const action = field.action === 'accept' ? 'Accepted' : field.action === 'edit' ? 'Corrected' : field.action === 'reject' ? 'Rejected' : displayValue(field.action); return <div key={index} className="p4-record-field-change"><div className="p4-record-field-header"><strong>{fieldLabel(String(field.fieldName ?? field.field ?? 'Field'))}</strong><span>{action}</span></div><dl className="p4-record-field-values"><div><dt>Original extracted value</dt><dd>{displayValue(field.originalValue)}</dd></div><div><dt>Human-reviewed value</dt><dd>{displayValue(field.reviewedValue)}{field.action === 'reject' ? <small>Field rejected · no value accepted by this decision</small> : null}</dd></div></dl><p>Reason: {text(field.reason) ?? 'No reason recorded.'}</p><small>{text(field.reviewerRole) ? displayRoleName(String(field.reviewerRole)) : 'Role not recorded'} · Reviewer ID {displayValue(field.reviewerId)} · {text(field.reviewedAt) ? displayDate(String(field.reviewedAt)) : 'Time not recorded'}</small></div> })}</div> : <p className="p4-section-copy">No saved field decisions are available for this attempt. Accepted, corrected, and rejected values appear here after review.</p>}<div className="p4-review-changes"><h3>Validation finding resolutions</h3>{resolutions.length ? resolutions.map((raw, index) => { const resolution = object(raw); return <div key={index}><strong>{displayValue(resolution.fieldName ? fieldLabel(String(resolution.fieldName)) : resolution.issueCode ?? resolution.code)}</strong><span>{text(resolution.resolution) ? titleCase(String(resolution.resolution)) : 'Resolution not recorded'}</span><p>Reason: {text(resolution.reason) ?? 'No reason recorded.'}</p><small>{text(resolution.actorRole) ? displayRoleName(String(resolution.actorRole)) : 'Role not recorded'} · Actor ID {displayValue(resolution.actorId)} · {text(resolution.at) ? displayDate(String(resolution.at)) : 'Time not recorded'}</small></div> }) : <p className="p4-section-copy">No finding resolutions were saved for this attempt. Original findings remain visible in Validation.</p>}</div></div>

  if (section === 'audit') return <div><div className="p4-section-heading"><div><span className="p4-eyebrow">Attributable workflow history</span><h2>Audit trail</h2></div><a className="p4-text-link" href={auditHref(String(record.recordId ?? ''))}>Full audit trail <ArrowRight size={14} aria-hidden="true" /></a></div><AuditTimeline events={detail.auditEvents || []} compact showRecordLinks={false} /></div>

  const hasGeometry = detail.parcel ? sourcedLeafletRing(detail.parcel) !== null : false
  return <div className="p4-card p4-record-section"><h2><MapPinned size={18} aria-hidden="true" /> GIS link</h2>
    {hasGeometry && detail.parcel ? <>
      <div className="p4-gis-progression" aria-label="Sourced parcel boundary available"><span>Final approval recorded</span><ArrowRight size={14} aria-hidden="true" /><span>Source recorded</span><ArrowRight size={14} aria-hidden="true" /><strong>Boundary available</strong></div>
      <DetailGrid values={[
        ['Survey number', detail.parcel.surveyNumber], ['Village', detail.parcel.village],
        ['Geometry source', detail.parcel.geometryReference], ['Source file', detail.parcel.geometryFileName],
        ['Recorded at', detail.parcel.geometryRecordedAt ? displayDate(detail.parcel.geometryRecordedAt) : null],
        ['Recorded by', detail.parcel.geometryRecordedBy],
      ]} />
      <a className="p4-primary-link" href={gisHref(detail.parcel.recordId)}>View on map <ArrowRight size={15} aria-hidden="true" /></a>
    </> : <>
      <p className="p4-section-copy"><strong>Parcel geometry unavailable.</strong> No boundary is inferred from this record. An authorized officer can import a sourced GeoJSON boundary after record approval.</p>
      <a className="p4-text-link" href={gisHref(String(record.recordId ?? ''))}>Open GIS workspace <ArrowRight size={14} aria-hidden="true" /></a>
    </>}
  </div>
}

export function RecordPage({ token, user, recordId }: Phase4PageProps & { recordId: string }) {
  const requestedSection = new URLSearchParams(window.location.hash.split('?')[1] ?? '').get('section')
  const section = sections.find((item) => item.id === requestedSection)?.id ?? 'overview'
  const canViewAudit = ['ADMIN', 'REVENUE_OFFICER', 'AUDITOR'].includes(user.role)
  const canViewGis = ['ADMIN', 'REVENUE_OFFICER', 'AUDITOR'].includes(user.role)
  const visibleSections = sections.filter((item) => (item.id !== 'audit' || canViewAudit) && (item.id !== 'gis' || canViewGis))
  const activeSection = visibleSections.some((item) => item.id === section) ? section : 'overview'
  const load = useCallback((signal: AbortSignal) => phase4Api.record(token, recordId, signal), [token, recordId])
  const { state, retry } = usePhase4Data(`record:${token}:${recordId}`, load)
  const record: CanonicalRecord = state.phase === 'ready' ? state.data.record : {}
  const review = state.phase === 'ready' ? object(state.data.review) : {}
  const officerStatus = text(review.status ?? review.reviewStatus)
  const routeStatus = text(record.validationStatus) ?? 'pending'
  const verified = officerStatus === 'approved'
  const headerStatus = state.phase === 'loading' ? 'Loading record' : state.phase === 'error' ? 'Record unavailable' : verified ? 'Officer approved · Final decision' : ['rejected', 'sent_back'].includes(officerStatus || '') ? `Final decision · ${finalDecision(review)}` : officerStatus ? `Review status · ${titleCase(officerStatus)}` : `Validation status · ${titleCase(routeStatus)}`
  const finalRole = state.phase === 'ready' ? decisionRole(state.data) : null
  const validation = object(review.validation)
  const score = number(review.qualityScore ?? object(review.scoreBreakdown).qualityScore ?? validation.qualityScore)

  return <section className="p4-page p4-record-page"><header className="p4-page-header"><div><span className="p4-eyebrow">Local record registry / human decisions</span><h1>{state.phase === 'ready' ? String(record.recordNumber || record.recordId || recordId) : 'Record detail'}</h1><p>Structured values, Evidence, Review history, the Audit trail, and sourced GIS geometry.</p></div><span className={`p4-header-status ${verified ? 'p4-header-status--verified' : ''}`}><ShieldCheck size={17} aria-hidden="true" />{headerStatus}</span></header>
    <div className="p4-inline-bar"><a href="#/records"><ArrowLeft size={15} aria-hidden="true" /> All records</a><span><strong>{displayRoleName(user.role)}</strong> · {user.name}</span><button type="button" onClick={retry}><RefreshCw size={14} aria-hidden="true" /> Refresh</button></div>
    {isQaWorkspace ? <p className="p4-qa-notice" role="note">Synthetic/test record · This isolated QA record is not an authoritative land record.</p> : null}
    {state.phase === 'loading' ? <div className="p4-loading" role="status"><span className="p4-spinner" />Loading record…</div> : null}
    {state.phase === 'error' ? <div className="p4-error" role="alert"><strong>Record unavailable</strong><span>{state.error}</span><button type="button" onClick={retry}>Retry</button></div> : null}
    {state.phase === 'ready' ? <><div className="p4-record-hero p4-card"><div><span>Processing quality score</span><strong>{score === null ? '—' : qualityScoreLabel(score)}<small> / 100</small></strong></div><div><span>Final decision date</span><strong>{review.decidedAt ? displayDate(String(review.decidedAt)) : 'Pending'}</strong></div><div><span>Final decision by</span><strong>{displayValue(review.decidedByName ?? review.decidedBy)}</strong>{finalRole ? <small className="p4-record-final-role">{displayRoleName(finalRole)}</small> : null}</div><div><span>Original source document</span><strong>{displayValue(object(record.sourceDocument).fileName)}</strong></div></div>
      <div className="p4-record-actions">{canViewGis ? <a className="p4-primary-link" href={gisHref(recordId)}><MapPinned size={15} aria-hidden="true" />View on map</a> : null}<a className="p4-text-link" href={reviewHref(recordId)}>{user.role === 'AUDITOR' ? 'Inspect review workspace' : 'Open review workspace'} <ArrowRight size={14} aria-hidden="true" /></a></div>
      <nav className="p4-record-nav" aria-label="Record sections">{visibleSections.map((item) => <button key={item.id} type="button" aria-pressed={activeSection === item.id} onClick={() => { window.location.hash = `${recordHref(recordId)}?section=${item.id}` }}>{item.label}</button>)}</nav>
      <div key={`${recordId}:${activeSection}`} className="p4-record-section-enter"><RecordBody detail={state.data} section={activeSection} /></div>
    </> : null}
  </section>
}
