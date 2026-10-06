export class ApiRequestError extends Error {
  readonly status?: number

  constructor(message: string, status?: number) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
  }
}

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/+$/, '')

export async function getJson(path: `/${string}`, signal?: AbortSignal): Promise<unknown> {
  let response: Response
  try {
    response = await fetch(`${apiBaseUrl}${path}`, {
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiRequestError('The API could not be reached. Check that the backend is running, then retry.')
  }

  if (!response.ok) throw new ApiRequestError(`The API returned HTTP ${response.status}.`, response.status)

  try {
    return await response.json() as unknown
  } catch {
    throw new ApiRequestError('The API returned an unreadable response.', response.status)
  }
}
