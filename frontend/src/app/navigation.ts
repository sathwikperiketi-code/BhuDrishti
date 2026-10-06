import {
  Activity,
  Archive,
  BarChart3,
  ClipboardCheck,
  FileStack,
  Files,
  FlaskConical,
  LayoutDashboard,
  MapPinned,
  Settings2,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

export type RouteId =
  | 'dashboard'
  | 'documents'
  | 'demo'
  | 'processing'
  | 'validation'
  | 'review-queue'
  | 'records'
  | 'gis'
  | 'analytics'
  | 'audit'
  | 'settings'

export interface NavigationItem {
  id: RouteId
  label: string
  icon: LucideIcon
  group: 'operations' | 'intelligence' | 'account'
  phase: 'available' | 'planned'
  description: string
}

export const navigationItems: NavigationItem[] = [
  { id: 'dashboard', label: 'Command Center', icon: LayoutDashboard, group: 'operations', phase: 'available', description: 'Operational overview from persisted records' },
  { id: 'documents', label: 'Documents', icon: Files, group: 'operations', phase: 'available', description: 'Upload and inspect document evidence' },
  { id: 'demo', label: 'Sample dataset', icon: FlaskConical, group: 'intelligence', phase: 'available', description: 'Read-only test documents, separate from operations' },
  { id: 'processing', label: 'Processing', icon: Activity, group: 'operations', phase: 'available', description: 'Live document processing status' },
  { id: 'validation', label: 'Validation', icon: ShieldCheck, group: 'operations', phase: 'available', description: 'Field, record, and reference checks' },
  { id: 'review-queue', label: 'Review Queue', icon: ClipboardCheck, group: 'operations', phase: 'available', description: 'Officer decision workflow' },
  { id: 'records', label: 'Records', icon: Archive, group: 'intelligence', phase: 'available', description: 'Structured record registry and verification history' },
  { id: 'gis', label: 'GIS Intelligence', icon: MapPinned, group: 'intelligence', phase: 'available', description: 'Verified records linked to prototype parcel geometry' },
  { id: 'analytics', label: 'Analytics', icon: BarChart3, group: 'intelligence', phase: 'available', description: 'Metrics from persisted prototype activity' },
  { id: 'audit', label: 'Audit Trail', icon: FileStack, group: 'intelligence', phase: 'available', description: 'Persistent attributed event history' },
  { id: 'settings', label: 'Settings', icon: Settings2, group: 'account', phase: 'available', description: 'Account, service status, and product boundaries' },
]

export const primaryMobileRoutes: RouteId[] = ['dashboard', 'documents', 'processing', 'validation']

export function navigationItem(route: RouteId): NavigationItem {
  return navigationItems.find((item) => item.id === route) ?? navigationItems[0]
}

export function routeHref(route: RouteId): string {
  return route === 'review-queue' ? '#/review' : `#/${route}`
}

export function routeFromHash(hash: string): RouteId {
  const value = hash.replace(/^#\/?/, '').split('?')[0]
  if (value === 'review' || value.startsWith('review/')) return 'review-queue'
  if (value.startsWith('records/')) return 'records'
  if (value.startsWith('audit/')) return 'audit'
  return navigationItems.find((item) => item.id === value)?.id ?? 'dashboard'
}

export function routeAvailableForRole(route: RouteId, role: string): boolean {
  if (role === 'VERIFIER') return !['processing', 'gis', 'audit'].includes(route)
  if (role === 'AUDITOR') return route !== 'processing'
  return role === 'ADMIN' || role === 'REVENUE_OFFICER'
}
