import { Component, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

interface Props { children: ReactNode }
interface State { hasError: boolean }

export class RouteErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State { return { hasError: true } }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <section className="bd-route-error" role="alert">
        <AlertTriangle size={27} aria-hidden="true" />
        <h1>Workspace view unavailable</h1>
        <p>The view could not be loaded. Your current data has not been changed.</p>
        <button type="button" onClick={() => window.location.reload()}><RotateCcw size={15} aria-hidden="true" />Reload view</button>
      </section>
    )
  }
}
