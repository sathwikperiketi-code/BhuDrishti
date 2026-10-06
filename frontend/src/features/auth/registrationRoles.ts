import type { SessionRole } from './session'

export type RequestedRole = SessionRole | ''

export const registrationRoles = [
  {
    value: 'REVENUE_OFFICER',
    title: 'Revenue Officer',
    description: 'Process land records, review extracted information, and handle permitted record decisions.',
    permissions: ['Upload and process', 'Review and decide'],
    action: 'Select Revenue Officer',
  },
  {
    value: 'VERIFIER',
    title: 'Verifier',
    description: 'Verify extracted fields, supporting evidence, and validation findings.',
    permissions: ['Inspect evidence', 'Recommend outcomes'],
    action: 'Select Verifier',
  },
  {
    value: 'AUDITOR',
    title: 'Auditor',
    description: 'Inspect records, validation results, and audit history with read-only access.',
    permissions: ['Read records', 'Inspect audit trail'],
    action: 'Select Auditor',
  },
  {
    value: 'ADMIN',
    title: 'Administrator',
    description: 'Manage users, permissions, and system operations after administrator approval.',
    permissions: ['Request access', 'Approval required'],
    action: 'Request Administrator Access',
  },
] as const satisfies ReadonlyArray<{
  value: SessionRole
  title: string
  description: string
  permissions: readonly string[]
  action: string
}>

export function registrationRoleLabel(role: RequestedRole): string {
  return registrationRoles.find((item) => item.value === role)?.title ?? ''
}
