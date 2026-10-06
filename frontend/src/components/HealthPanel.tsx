import { Activity, RefreshCw, CircleAlert, CircleCheck, Server, ShieldCheck } from 'lucide-react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { useHealth } from '../hooks/useHealth'

export function HealthPanel() {
  const { state, retry } = useHealth()
  const reduceMotion = useReducedMotion()
  const transition = { duration: reduceMotion ? 0 : 0.2 }
  const initial = reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }
  const exit = reduceMotion ? { opacity: 1 } : { opacity: 0, y: -8 }

  return (
    <div className="overflow-hidden rounded-[18px] border border-[#dce6e2] bg-white shadow-[0_12px_35px_-34px_rgba(16,36,45,0.5)]">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#e4ece8] px-5 py-4 sm:px-7">
        <div className="flex items-center gap-2.5">
          <Activity className="h-4.5 w-4.5 text-[#3f8270]" strokeWidth={1.8} aria-hidden="true" />
          <h3 className="text-sm font-semibold text-[#24434a]">Backend connection</h3>
        </div>
        <code className="rounded-md bg-[#f0f5f2] px-2.5 py-1.5 text-[11px] font-medium text-[#658078]">GET /api/v1/health</code>
      </div>

      <div aria-live="polite" aria-atomic="true" className="min-h-[214px] px-5 py-6 sm:px-7">
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={state.phase} initial={initial} animate={{ opacity: 1, y: 0 }} exit={exit} transition={transition}>
            {state.phase === 'loading' && (
              <div role="status" className="flex min-h-[162px] items-center gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#edf3f0] text-[#53806f]"><Server className="h-6 w-6" strokeWidth={1.6} aria-hidden="true" /></div>
                <div><p className="text-base font-semibold text-[#234049]">Checking API availability</p><p className="mt-1 text-sm text-[#7d918d]">Waiting for a response from the backend service.</p></div>
              </div>
            )}

            {state.phase === 'error' && (
              <div className="flex min-h-[162px] flex-col justify-center gap-5 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-4">
                  <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-[#fbf0ed] text-[#b76b52]"><CircleAlert className="h-6 w-6" strokeWidth={1.7} aria-hidden="true" /></div>
                  <div><p className="text-base font-semibold text-[#5e3c32]">API unavailable</p><p className="mt-1 max-w-xl text-sm leading-6 text-[#866e67]">{state.message}</p></div>
                </div>
                <button type="button" onClick={retry} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-lg border border-[#b9d6c7] bg-white px-4 text-xs font-semibold text-[#2d705e] transition-colors hover:bg-[#f0f7f2] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2d7565]">
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />Retry connection
                </button>
              </div>
            )}

            {state.phase === 'ready' && (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(300px,0.8fr)]">
                <div className="flex items-start gap-4">
                  <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${state.data.status === 'ok' ? 'bg-[#eaf5ee] text-[#43866b]' : 'bg-[#fff3e6] text-[#b67b3d]'}`}>
                    {state.data.status === 'ok' ? <CircleCheck className="h-6 w-6" strokeWidth={1.7} aria-hidden="true" /> : <CircleAlert className="h-6 w-6" strokeWidth={1.7} aria-hidden="true" />}
                  </div>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-base font-semibold text-[#234049]">{state.data.status === 'ok' ? 'API responding' : `API status: ${state.data.status}`}</p>
                      <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.1em] ${state.data.status === 'ok' ? 'bg-[#ebf5ed] text-[#458469]' : 'bg-[#fff2e1] text-[#ac7438]'}`}>{state.data.status}</span>
                    </div>
                    <p className="mt-1 text-sm leading-6 text-[#758b85]">{state.data.service}</p>
                    <p className="mt-5 text-xs text-[#8fa09b]">Checked at {state.checkedAt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</p>
                  </div>
                </div>

                <dl className="grid grid-cols-2 gap-x-5 gap-y-4 rounded-xl border border-[#e5ece8] bg-[#f9fbfa] p-4 text-xs">
                  <div><dt className="mb-1 text-[10px] font-bold uppercase tracking-[0.11em] text-[#94a7a0]">Version</dt><dd className="font-semibold text-[#365850]">{state.data.version}</dd></div>
                  <div><dt className="mb-1 text-[10px] font-bold uppercase tracking-[0.11em] text-[#94a7a0]">Environment</dt><dd className="font-semibold capitalize text-[#365850]">{state.data.environment}</dd></div>
                  <div className="col-span-2 border-t border-[#e4ece8] pt-3">
                    <dt className="mb-1 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.11em] text-[#94a7a0]"><ShieldCheck className="h-3 w-3" aria-hidden="true" />Document provider</dt>
                    <dd className="font-semibold text-[#365850]">{state.data.provider.provider} · {state.data.provider.available ? 'available' : 'unavailable'}</dd>
                    <dd className="mt-1 text-[11px] leading-4 text-[#849892]">{state.data.provider.message ?? 'No provider details supplied.'}</dd>
                  </div>
                </dl>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}
