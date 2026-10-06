/** Presentation labels only; authorization remains in the existing backend. */
export function displayRoleName(role: string): string {
  switch (role) {
    case 'REVENUE_OFFICER': return 'Revenue Officer'
    case 'VERIFIER': return 'Verifier'
    case 'AUDITOR': return 'Auditor'
    case 'ADMIN': return 'Administrator'
    case 'SYSTEM': return 'System'
    default: return role.replaceAll('_', ' ')
  }
}
