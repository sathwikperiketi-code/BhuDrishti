import { getJson, ApiRequestError } from './client'
import { isHealthResponse } from '../types/health'
import type { HealthResponse } from '../types/health'

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const response = await getJson('/health', signal)
  if (!isHealthResponse(response)) throw new ApiRequestError('The API health response did not match its contract.')
  return response
}
