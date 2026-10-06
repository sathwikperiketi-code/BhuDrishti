export function isRevenueOfficerPreviewRoute(hash: string, development: boolean, hostname: string): boolean {
  return development
    && ['localhost', '127.0.0.1', '[::1]', '::1'].includes(hostname)
    && hash.split('?')[0] === '#/dev/revenue-officer'
}
