import { ArrowLeft, Construction, LockKeyhole } from 'lucide-react'
import { navigationItem, routeHref, type RouteId } from './navigation'

interface PlannedPageProps {
  route: RouteId
}

export function PlannedPage({ route }: PlannedPageProps) {
  const item = navigationItem(route)
  return (
    <section className="bd-planned-page" aria-labelledby="bd-planned-title">
      <div className="bd-page-kicker"><span className="bd-kicker-dot" />MODULE PREVIEW · FUTURE PHASE</div>
      <div className="bd-planned-panel">
        <div className="bd-planned-icon">{route === 'settings' ? <LockKeyhole size={25} aria-hidden="true" /> : <Construction size={25} aria-hidden="true" />}</div>
        <p className="bd-planned-eyebrow">Planned workflow</p>
        <h1 id="bd-planned-title">{item.label}</h1>
        <p>{item.description}. This screen is reserved in the navigation while the underlying service and permissions are built.</p>
        {route === 'review-queue' && <p>The current validation preview shows how a discrepancy will enter officer review. No approval action is available yet.</p>}
        <a href={routeHref(route === 'review-queue' ? 'validation' : 'dashboard')}><ArrowLeft size={16} aria-hidden="true" />{route === 'review-queue' ? 'View validation preview' : 'Return to Command Center'}</a>
      </div>
    </section>
  )
}
