import { useEffect, useRef } from 'react'
import { useReducedMotion } from 'framer-motion'
import { formatCount } from './operationsData'

/** Animate the presentation once; the accessible value is always the server total. */
export function MetricValue({ value, animate }: { value: number; animate: boolean }) {
  const element = useRef<HTMLSpanElement>(null)
  const started = useRef(false)
  const reducedMotion = useReducedMotion()
  useEffect(() => {
    const node = element.current
    if (!node) return
    node.textContent = formatCount(value)
    if (started.current || !animate || reducedMotion || !Number.isFinite(value) || value <= 0) return
    started.current = true
    const start = performance.now()
    let frame = 0
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / 600)
      node.textContent = formatCount(Math.round(value * (1 - (1 - progress) ** 3)))
      if (progress < 1) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => {
      cancelAnimationFrame(frame)
      node.textContent = formatCount(value)
    }
  }, [value, animate, reducedMotion])
  return <><span ref={element} aria-hidden="true">{formatCount(value)}</span><span className="sr-only">{formatCount(value)}</span></>
}
