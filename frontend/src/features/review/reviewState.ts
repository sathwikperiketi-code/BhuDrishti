import type { IssueResolution, ReviewField } from './types'

/** Only a saved accept/edit is an accepted value. The AI snapshot stays separate. */
export function acceptedFieldValue(field: ReviewField): unknown {
  if (field.reviewStatus === 'accept') return field.reviewedValue ?? field.originalValue
  if (field.reviewStatus === 'edit') return field.reviewedValue
  return null
}

export function resolutionForIssue(resolutions: IssueResolution[], code: string, fieldName: string | null) {
  return resolutions.find((entry) => entry.issueCode === code && (entry.fieldName ?? null) === fieldName)
}

export function isClearValidation(status: string | null | undefined) {
  return Boolean(status && ['clear', 'valid', 'pass', 'passed'].includes(status.toLowerCase()))
}
