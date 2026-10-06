import { ArrowRight, Check, CircleAlert, ClipboardPenLine, DatabaseZap, FileCheck2, FileUp, MapPinned, ScanText, ShieldAlert, ShieldCheck, UserRoundCheck } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { auditHref, auditResult, displayDate, displayValue, eventLabel, eventTone, fieldLabel, recordHref } from './format'
import { displayRoleName } from '../../lib/roles'
import type { AuditEvent } from './types'

const eventIcons: Record<string, LucideIcon> = {
  DOCUMENT_UPLOADED: FileUp,
  PROCESSING_STARTED: DatabaseZap,
  PREPROCESSING_COMPLETED: FileCheck2,
  OCR_COMPLETED: ScanText,
  EXTRACTION_COMPLETED: ScanText,
  VALIDATION_COMPLETED: ShieldCheck,
  CONFLICT_DETECTED: ShieldAlert,
  REVIEW_STARTED: UserRoundCheck,
  FIELD_EDITED: ClipboardPenLine,
  FIELD_ACCEPTED: Check,
  FIELD_REJECTED: CircleAlert,
  ISSUE_RESOLVED: Check,
  REVIEW_RECOMMENDED: ClipboardPenLine,
  RECORD_APPROVED: ShieldCheck,
  RECORD_REJECTED: CircleAlert,
  RECORD_SENT_BACK: ArrowRight,
  GIS_INDEXED: MapPinned,
  GEOMETRY_IMPORTED: MapPinned,
  GEOMETRY_REPLACED: MapPinned,
}

function actor(event: AuditEvent): string {
  if (event.actorName) return event.actorName
  if (event.actorRole === 'SYSTEM') return 'BhuDrishti system'
  return event.actorId || 'System event'
}

function change(event: AuditEvent) {
  const metadata = event.metadata || {}
  const previousKey = ['previousValue', 'originalValue', 'before'].find((key) => Object.hasOwn(metadata, key))
  const nextKey = ['newValue', 'reviewedValue', 'after'].find((key) => Object.hasOwn(metadata, key))
  const previous = previousKey ? metadata[previousKey] : undefined
  const next = nextKey ? metadata[nextKey] : undefined
  if (previous === undefined && next === undefined) return null
  return { previous, next, field: event.metadata?.fieldName ?? event.metadata?.field }
}

function metadataEntries(event: AuditEvent) {
  return Object.entries(event.metadata || {}).filter(([, value]) => value !== null && value !== undefined)
}

export function AuditTimeline({ events, compact = false, showRecordLinks = true }: { events: AuditEvent[]; compact?: boolean; showRecordLinks?: boolean }) {
  if (events.length === 0) return <div className="p4-empty"><FileCheck2 size={24} aria-hidden="true" /><strong>No audit events in this view</strong><span>Stored upload, processing, review, final-decision, and geometry events appear here. Change the filters or return after workflow activity occurs.</span></div>
  return <ol className={`p4-timeline ${compact ? 'p4-timeline--compact' : ''}`} aria-label="Audit events">
    {events.map((event) => {
      const Icon = eventIcons[event.eventType] || FileCheck2
      const tone = eventTone(event.eventType)
      const values = change(event)
      const entries = metadataEntries(event)
      const description = event.description && typeof values?.field === 'string'
        ? event.description.replaceAll(values.field, fieldLabel(values.field).toLowerCase())
        : event.description
      return <li className="p4-timeline-item" key={event.id}>
        <span className={`p4-timeline-icon p4-timeline-icon--${tone}`}><Icon size={16} strokeWidth={1.8} aria-hidden="true" /></span>
        <div className="p4-timeline-card">
          <div className="p4-timeline-top"><div><span className="p4-eyebrow">Action</span><h3>{eventLabel(event)}</h3>{description ? <p className="p4-event-description">{description}</p> : null}</div><div className="p4-event-time"><span className="p4-eyebrow">Timestamp</span><time dateTime={event.timestamp}>{displayDate(event.timestamp, { dateStyle: 'medium', timeStyle: 'long' })}</time></div></div>
          <dl className="p4-audit-facts"><div><dt>Actor</dt><dd>{actor(event)}</dd></div><div><dt>Role</dt><dd>{event.actorRole ? displayRoleName(event.actorRole) : 'Not recorded'}</dd></div><div className="p4-audit-reason"><dt>Reason</dt><dd>{displayValue(event.metadata?.reason) === '—' ? 'No reason recorded for this event.' : displayValue(event.metadata.reason)}</dd></div><div className="p4-audit-result"><dt>Result</dt><dd>{auditResult(event)}</dd></div></dl>
          {showRecordLinks && event.recordId ? <div className="p4-timeline-meta"><a href={recordHref(event.recordId)}>Open record <ArrowRight size={13} aria-hidden="true" /></a></div> : null}
          {values ? <div className="p4-change"><span>{typeof values.field === 'string' ? fieldLabel(values.field) : 'Field change'} · Before → After</span><div><del>{displayValue(values.previous)}</del><ArrowRight size={14} aria-hidden="true" /><strong>{displayValue(values.next)}</strong></div></div> : null}
          {entries.length ? <details className="p4-audit-details"><summary>Event metadata <span>{entries.length} item{entries.length === 1 ? '' : 's'}</span></summary><dl>{entries.map(([key, value]) => <div key={key}><dt>{fieldLabel(key)}</dt><dd>{displayValue(value)}</dd></div>)}</dl></details> : null}
          {!showRecordLinks && event.recordId && !compact ? <a className="p4-timeline-context" href={auditHref(event.recordId)}>View this record’s full history</a> : null}
        </div>
      </li>
    })}
  </ol>
}
