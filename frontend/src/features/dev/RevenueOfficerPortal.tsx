import { AppShell } from '../../app/AppShell'
import type { SessionUser } from '../auth/session'
import { DashboardPage } from '../dashboard'
import type { OperationsData } from '../dashboard/operationsData'

// Presentation only: never an AuthSession, stored account, or bearer credential.
const previewUser: SessionUser = {
  id: 'development-ui-preview', name: 'Development preview',
  email: 'ui-preview@example.invalid', role: 'REVENUE_OFFICER',
}
const previewData: OperationsData = {
  summary: {
    source: 'development-ui-preview',
    disclaimer: 'Synthetic empty preview data for UI inspection. No authenticated records are loaded.',
    generatedAt: new Date().toISOString(),
    metrics: {
      documentsTotal: 0, documentsProcessed: 0, processingFailed: 0, recordsTotal: 0,
      awaitingReview: 0, validationConflicts: 0, approvedRecords: 0,
      approvalRate: null, reviewRate: null, conflictRate: null, averageQualityScore: null,
    },
    processingVolume: [], validationDistribution: [], processingStatusDistribution: [], recentActivity: [],
    definitions: { approvalRate: '', reviewRate: '', conflictRate: '', validationConflicts: '' },
  },
  reviews: [], documents: [],
}

export default function RevenueOfficerPortal() {
  if (!import.meta.env.DEV) return null
  return <AppShell currentRoute="dashboard" token="" user={previewUser} developmentPreview
    onLogout={() => { window.location.hash = '#/login' }}>
    <div className="bd-qa-banner" role="note">
      <strong>Local development · Revenue Officer UI preview</strong>
      <span>Synthetic empty data. No login or API permissions are granted. Workspace links return to the normal authenticated application.</span>
    </div>
    <DashboardPage token="" role={previewUser.role} developmentData={previewData} />
  </AppShell>
}
