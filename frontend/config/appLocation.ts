/** Keep Vite's binding aligned with the URL used in account email links. */
export function appLocation(value = 'http://localhost:5173') {
  let url: URL
  try { url = new URL(value) } catch { throw new Error('VITE_APP_URL must be an absolute http(s) frontend URL.') }
  if (!['http:', 'https:'].includes(url.protocol) || !url.hostname || url.username || url.password || url.search || url.hash || /\s/.test(value)) {
    throw new Error('VITE_APP_URL must be an absolute http(s) frontend URL without credentials, query, or fragment.')
  }
  return {
    host: url.hostname.replace(/^\[|\]$/g, ''),
    port: Number(url.port || (url.protocol === 'https:' ? 443 : 80)),
    origin: url.origin,
    base: `${url.pathname.replace(/\/+$/, '')}/`,
  }
}
