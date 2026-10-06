import type { paths } from './api.generated'

/** The backend OpenAPI response is the source of truth; runtime shape is checked at the HTTP boundary. */
export type HealthResponse = paths['/api/v1/health']['get']['responses'][200]['content']['application/json']

export function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== 'object' || value === null) return false
  const response = value as Record<string, unknown>
  if (typeof response.provider !== 'object' || response.provider === null) return false
  const provider = response.provider as Record<string, unknown>

  return typeof response.status === 'string'
    && typeof response.service === 'string'
    && typeof response.version === 'string'
    && typeof response.environment === 'string'
    && typeof provider.provider === 'string'
    && typeof provider.available === 'boolean'
    && (provider.pdfTextAvailable === undefined || typeof provider.pdfTextAvailable === 'boolean')
    && (provider.ocrAvailable === undefined || typeof provider.ocrAvailable === 'boolean')
    && (provider.installedLanguages === undefined || Array.isArray(provider.installedLanguages))
    && (provider.unsupportedLanguages === undefined || Array.isArray(provider.unsupportedLanguages))
    && (provider.message === undefined || provider.message === null || typeof provider.message === 'string')
}
