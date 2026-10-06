export interface AuditEvent {
  id: string
  recordId: string | null
  documentId: string | null
  actorId: string
  actorName?: string | null
  actorRole: string
  eventType: string
  timestamp: string
  description: string
  metadata: Record<string, unknown>
}

export interface AuditListResponse { items: AuditEvent[]; total: number }

export interface GisParcel {
  recordId: string
  recordNumber: string | null
  surveyNumber: string | null
  ownerName: string | null
  area: number | null
  areaUnit: string | null
  village: string | null
  district: string | null
  state: string | null
  status: string
  validationStatus: string
  qualityScore: number | null
  /** GeoJSON exterior ring in [longitude, latitude] order. Never a virtual grid. */
  polygon: number[][] | null
  geometryStatus: 'unavailable' | 'sourced'
  geometrySource: string | null
  geometryReference: string | null
  geometryFileName: string | null
  geometrySha256: string | null
  geometryRecordedAt: string | null
  geometryRecordedBy: string | null
  indexedAt: string | null
}

export interface GisListResponse { items: GisParcel[]; total: number; synthetic: false; disclaimer: string }

export interface Phase4User { id: string; name: string; role: string }

export interface Phase4PageProps { token: string; user: Phase4User }

export type CanonicalRecord = Record<string, unknown> & { recordId?: string; sourceDocument?: Record<string, unknown>; provenance?: Record<string, unknown> }

export interface RecordDetailResponse {
  record: CanonicalRecord
  review: Record<string, unknown> | null
  auditEvents: AuditEvent[]
  parcel: GisParcel | null
}

export interface RecordListItem {
  id?: string
  recordId?: string
  recordNumber?: string | null
  ownerName?: string | null
  surveyNumber?: string | null
  village?: string | null
  district?: string | null
  validationStatus?: string | null
  recordStatus?: string | null
  qualityScore?: number | null
  updatedAt?: string | null
}

export interface RecordsListResponse { items: RecordListItem[]; total: number }

export interface NotificationItem {
  id: string
  eventType: string
  recordId: string | null
  timestamp: string
  description: string
  actorId?: string | null
  actorRole?: string | null
  metadata?: Record<string, unknown>
  title?: string | null
  href?: string | null
  read?: boolean
}

export interface NotificationsResponse { items: NotificationItem[]; total: number }
