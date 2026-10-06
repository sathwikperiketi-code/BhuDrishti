import { useReducedMotion } from 'framer-motion'
import { useState, type ReactNode } from 'react'
import { MetricValue } from './MetricValue'
import './dashboard.css'
import { Activity, ArrowRight, CheckCircle2, CircleAlert, Clock3, FileText, RefreshCw, ShieldCheck, Upload } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useHealth } from '../../hooks/useHealth'
import type { DocumentSummary } from '../live/types'
import type { ReviewCaseSummary } from '../review/types'
import { formatCount, operationLabel, readableDate, useOperationsData, type AnalyticsSummary, type OperationsData } from './operationsData'
import { displayRoleName } from '../../lib/roles'

const panelClass = 'bd-dashboard-panel min-w-0 overflow-hidden rounded-xl border border-[var(--bd-border)] bg-white shadow-[var(--bd-shadow-sm)]'

function Panel({ eyebrow, title, action, children }: { eyebrow: string; title: string; action?: ReactNode; children: ReactNode }) {
  return <section className={panelClass} aria-label={title}>
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--bd-border)] px-5 py-4">
      <div><p className="text-[10px] font-bold uppercase tracking-[.14em] text-[var(--bd-text-subtle)]">{eyebrow}</p><h2 className="mt-1 text-[15px] font-semibold tracking-[-.02em] text-[var(--bd-text)]">{title}</h2></div>
      {action}
    </div>
    {children}
  </section>
}

function Empty({ title, detail, href, action }: { title: string; detail: string; href?: string; action?: string }) {
  return <div className="flex min-h-[170px] flex-col items-center justify-center gap-2 px-6 py-8 text-center">
    <FileText size={23} className="text-[var(--bd-text-subtle)]" aria-hidden="true" />
    <strong className="text-sm text-[var(--bd-text)]">{title}</strong>
    <p className="max-w-[310px] text-xs leading-5 text-[var(--bd-text-muted)]">{detail}</p>
    {href && <a className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-[var(--bd-accent)] underline-offset-2 hover:underline" href={href}>{action}<ArrowRight size={13} aria-hidden="true" /></a>}
  </div>
}

function OverviewMetrics({ summary, role, animate }: { summary: AnalyticsSummary; role: string; animate: boolean }) {
  const m = summary.metrics
  const cells = [
    { label: 'Awaiting review', value: m.awaitingReview, sub: 'Open human-review cases', tone: 'border-t-[var(--bd-warning)]', href: '#/review' },
    { label: 'Processing failed', value: m.processingFailed, sub: role === 'ADMIN' || role === 'REVENUE_OFFICER' ? 'Inspect and retry eligible sources' : 'Officer attention required', tone: 'border-t-[var(--bd-danger)]', href: role === 'ADMIN' || role === 'REVENUE_OFFICER' ? '#/processing' : '#/documents' },
    { label: 'Validation conflicts', value: m.validationConflicts, sub: 'Original processing findings', tone: 'border-t-[var(--bd-danger)]', href: '#/validation' },
    { label: 'Documents processed', value: m.documentsProcessed, sub: `${formatCount(m.documentsTotal)} received · review still required`, tone: 'border-t-[var(--bd-info)]', href: '#/documents' },
    { label: 'Approved records', value: m.approvedRecords, sub: 'Final human approval recorded', tone: 'border-t-[var(--bd-success)]', href: '#/records' },
  ]
  return <div className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-5" aria-label="Current persisted workflow totals">
    {cells.map((item) => <a key={item.label} href={item.href} className={`${panelClass} ${item.tone} bd-dashboard-metric group flex min-h-[125px] flex-col justify-between border-t-[3px] px-4 py-4 transition-shadow hover:shadow-[var(--bd-shadow-md)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--bd-info)]`}>
      <span className="text-[11px] font-semibold leading-4 text-[var(--bd-text-muted)]">{item.label}</span>
      <span className="text-[clamp(1.6rem,2.1vw,2rem)] font-semibold leading-none tracking-[-.055em] tabular-nums text-[var(--bd-text)]">{<MetricValue value={item.value} animate={animate} />}</span>
      <span className="flex items-center justify-between gap-2 text-[10px] text-[var(--bd-text-subtle)]">{item.sub}<ArrowRight size={12} className="shrink-0 opacity-0 transition-opacity group-hover:opacity-100" aria-hidden="true" /></span>
    </a>)}
  </div>
}

function VolumeChart({ summary, reducedMotion }: { summary: AnalyticsSummary; reducedMotion: boolean }) {
  const data = summary.processingVolume.slice(-14).map((item) => ({ ...item, label: new Date(`${item.date}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }))
  return <Panel eyebrow="Throughput" title="Processing volume" action={<span className="text-[10px] text-[var(--bd-text-subtle)]">Recent {data.length} days</span>}>
    {data.length === 0 || data.every((point) => point.count === 0)
      ? <Empty title="No completed processing yet" detail="Upload and process a document to build a measured activity history." href="#/documents" action="Open documents" />
      : <div className="px-3 pb-3 pt-4 sm:px-5"><div role="img" aria-label={`Processed documents by day: ${data.map((point) => `${point.label} ${point.count}`).join(', ')}`} className="h-[210px] w-full">
        <ResponsiveContainer width="100%" height="100%"><BarChart data={data} margin={{ top: 8, right: 6, bottom: 0, left: -24 }} accessibilityLayer><CartesianGrid vertical={false} stroke="#e9efed" /><XAxis dataKey="label" axisLine={false} tickLine={false} tick={{ fill: '#647982', fontSize: 10 }} dy={7} /><YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fill: '#647982', fontSize: 10 }} /><Tooltip cursor={{ fill: '#f0f5f2' }} contentStyle={{ border: '1px solid #dce7e2', borderRadius: 8, fontSize: 11 }} /><Bar dataKey="count" name="Processed" fill="#286c90" radius={[3, 3, 0, 0]} maxBarSize={30} isAnimationActive={!reducedMotion} /></BarChart></ResponsiveContainer>
      </div><p className="border-t border-[var(--bd-border)] px-2 pt-3 text-[10px] text-[var(--bd-text-subtle)]">Each bar counts processed source documents in the local prototype database.</p></div>}
  </Panel>
}

function ValidationMix({ summary }: { summary: AnalyticsSummary }) {
  const items = summary.validationDistribution.filter((item) => item.count > 0)
  const total = items.reduce((value, item) => value + item.count, 0)
  const color = (status: string) => /conflict|reject|fail/i.test(status) ? 'bg-[var(--bd-danger)]' : /review|warning|pending/i.test(status) ? 'bg-[var(--bd-warning)]' : /approv|valid|pass|clear/i.test(status) ? 'bg-[var(--bd-success)]' : 'bg-[var(--bd-info)]'
  return <Panel eyebrow="Validation" title="Routing distribution" action={<span className="text-[10px] text-[var(--bd-text-subtle)]">{formatCount(total)} processed documents</span>}>
    {total === 0 ? <Empty title="No validation results yet" detail="Results appear after a document completes validation." /> : <div className="space-y-4 px-5 py-5">
      {items.map((item) => <div key={item.status}><div className="mb-1.5 flex items-center justify-between gap-2 text-[11px]"><span className="text-[var(--bd-text-muted)]">{operationLabel(item.status)}</span><strong className="tabular-nums text-[var(--bd-text)]">{formatCount(item.count)} <span className="font-medium text-[var(--bd-text-subtle)]">({Math.round(item.count / total * 100)}%)</span></strong></div><div className="h-2 overflow-hidden rounded-full bg-[#edf1ef]" role="progressbar" aria-label={operationLabel(item.status)} aria-valuenow={item.count} aria-valuemin={0} aria-valuemax={total}><div className={`bd-dashboard-fill h-full rounded-full ${color(item.status)}`} style={{ width: `${item.count / total * 100}%` }} /></div></div>)}
      <p className="border-t border-[var(--bd-border)] pt-3 text-[11px] leading-5 text-[var(--bd-text-muted)]">Routing comes from backend validation of extracted evidence. A record becomes verified only after an officer approves it.</p>
    </div>}
  </Panel>
}

function ReviewQueue({ items }: { items: ReviewCaseSummary[] }) {
  return <Panel eyebrow="Human oversight" title="Review queue" action={<a href="#/review" className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--bd-accent)] hover:underline">View all <ArrowRight size={13} aria-hidden="true" /></a>}>
    {items.length === 0 ? <Empty title="No open review cases" detail="Every processed operational source creates a human-review case. Completed decisions remain available in Records and the audit trail." href="#/records" action="Open records" /> : <ul className="divide-y divide-[var(--bd-border)]">
      {items.map((item) => <li key={item.recordId}><a href={`#/review/${encodeURIComponent(item.recordId)}`} className="group flex items-start gap-3 px-5 py-3.5 hover:bg-[var(--bd-surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--bd-info)]">
        <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md ${item.priority === 'high' ? 'bg-[var(--bd-danger-soft)] text-[var(--bd-danger)]' : 'bg-[var(--bd-warning-soft)] text-[var(--bd-warning)]'}`}><CircleAlert size={16} aria-hidden="true" /></span>
        <span className="min-w-0 flex-1"><span className="flex items-start justify-between gap-2"><strong className="min-w-0 truncate text-xs text-[var(--bd-text)]">{item.recordNumber || item.documentName}</strong><span className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${item.priority === 'high' ? 'bg-[var(--bd-danger-soft)] text-[var(--bd-danger)]' : 'bg-[var(--bd-warning-soft)] text-[var(--bd-warning)]'}`}>{item.priority}</span></span><span className="mt-1 block truncate text-[10px] text-[var(--bd-text-muted)]">{item.ownerName || 'Owner pending'} · Survey {item.surveyNumber || 'pending'}</span><span className="mt-1.5 block truncate text-[10px] text-[var(--bd-text-subtle)]">{item.primaryConflict || item.priorityReasons[0] || 'Verification required'}</span></span><ArrowRight size={14} className="mt-2 shrink-0 text-[var(--bd-accent)] opacity-0 group-hover:opacity-100" aria-hidden="true" />
      </a></li>)}
    </ul>}
  </Panel>
}

function RecentDocuments({ items, canUpload }: { items: DocumentSummary[]; canUpload: boolean }) {
  return <Panel eyebrow="Intake" title="Recent documents" action={<a href="#/documents" className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--bd-accent)] hover:underline">View all <ArrowRight size={13} aria-hidden="true" /></a>}>
    {items.length === 0 ? <Empty title="No documents uploaded" detail={canUpload ? 'Upload a PDF or image to store the source, extract text, and begin human review.' : 'Source records will appear here when a Revenue Officer or Administrator uploads them. You can then inspect the evidence.'} href="#/documents" action={canUpload ? 'Upload a document' : 'Open documents'} /> : <ul className="divide-y divide-[var(--bd-border)]">
      {items.slice(0, 4).map((item) => <li key={item.id}><a href={`#/documents?id=${encodeURIComponent(item.id)}`} className="flex items-center gap-3 px-5 py-3.5 hover:bg-[var(--bd-surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--bd-info)]"><span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-[var(--bd-info-soft)] text-[var(--bd-info)]"><FileText size={15} aria-hidden="true" /></span><span className="min-w-0 flex-1"><strong className="block truncate text-xs text-[var(--bd-text)]">{item.fileName}</strong><small className="mt-1 block text-[10px] text-[var(--bd-text-subtle)]">{readableDate(item.uploadedAt)} · {item.id.slice(0, 8)}</small></span><span className={`shrink-0 rounded px-2 py-1 text-[10px] font-semibold ${item.status === 'completed' ? 'bg-[var(--bd-success-soft)] text-[var(--bd-success)]' : item.status === 'failed' ? 'bg-[var(--bd-danger-soft)] text-[var(--bd-danger)]' : 'bg-[var(--bd-info-soft)] text-[var(--bd-info)]'}`}>{operationLabel(item.status)}</span></a></li>)}
    </ul>}
  </Panel>
}

function RecentActivity({ items, role }: { items: AnalyticsSummary['recentActivity']; role: string }) {
  return <Panel eyebrow="Audit signals" title="Recent activity" action={role === 'VERIFIER' ? undefined : <a href="#/audit" className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--bd-accent)] hover:underline">Audit trail <ArrowRight size={13} aria-hidden="true" /></a>}>
    {items.length === 0 ? <Empty title="No workflow activity yet" detail="Processing and review actions will appear here as they happen." /> : <ol className="divide-y divide-[var(--bd-border)]">
      {items.slice(0, 5).map((item) => <li key={item.id}><a href={role === 'VERIFIER' && item.href.startsWith('#/audit') ? '#/records' : item.href.startsWith('#/') ? item.href : role === 'VERIFIER' ? '#/records' : '#/audit'} className="flex items-start gap-3 px-5 py-3 hover:bg-[var(--bd-surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--bd-info)]"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-[var(--bd-info)]" aria-hidden="true" /><span className="min-w-0 flex-1"><strong className="block truncate text-[11px] font-semibold text-[var(--bd-text)]">{item.title || operationLabel(item.eventType)}</strong><time dateTime={item.timestamp} className="mt-1 block text-[10px] text-[var(--bd-text-subtle)]">{readableDate(item.timestamp)}</time></span><ArrowRight size={13} className="mt-1 shrink-0 text-[var(--bd-accent)]" aria-hidden="true" /></a></li>)}
    </ol>}
  </Panel>
}

function SystemHealth({ failed }: { failed: number }) {
  const { state, retry } = useHealth()
  return <Panel eyebrow="Service status" title="Processing health" action={<Activity size={16} className="text-[var(--bd-info)]" aria-hidden="true" />}>
    <div className="px-5 py-5" aria-live="polite">
      {state.phase === 'loading' && <p role="status" className="text-xs text-[var(--bd-text-muted)]">Checking the processing API…</p>}
      {state.phase === 'error' && <div className="space-y-3"><p className="flex items-center gap-2 text-xs font-semibold text-[var(--bd-danger)]"><CircleAlert size={16} aria-hidden="true" />Service unavailable</p><p className="text-xs leading-5 text-[var(--bd-text-muted)]">{state.message}</p><button type="button" onClick={retry} className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--bd-accent)] hover:underline"><RefreshCw size={13} aria-hidden="true" />Retry health check</button></div>}
      {state.phase === 'ready' && <div className="space-y-3"><p className={`flex items-center gap-2 text-xs font-semibold ${state.data.status === 'ok' ? 'text-[var(--bd-success)]' : 'text-[var(--bd-warning)]'}`}>{state.data.status === 'ok' ? <CheckCircle2 size={17} aria-hidden="true" /> : <CircleAlert size={17} aria-hidden="true" />}{state.data.status === 'ok' ? 'API responding' : `API status: ${state.data.status}`}</p><p className="text-xs text-[var(--bd-text-muted)]">{failed === 0 ? 'No failed documents in this dataset.' : `${formatCount(failed)} document${failed === 1 ? '' : 's'} need processing attention.`}</p><p className="border-t border-[var(--bd-border)] pt-3 text-[10px] text-[var(--bd-text-subtle)]">{state.data.provider.provider} · Checked {state.checkedAt.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}</p></div>}
    </div>
  </Panel>
}

function DigitizationProgress({ summary }: { summary: AnalyticsSummary }) {
  const m = summary.metrics
  const base = m.documentsTotal
  const stages = [
    { label: 'Document intake', count: m.documentsTotal, percent: base ? 100 : 0, color: 'bg-[var(--bd-info)]' },
    { label: 'Processing complete', count: m.documentsProcessed, percent: base ? Math.min(100, m.documentsProcessed / base * 100) : 0, color: 'bg-[var(--bd-accent)]' },
    { label: 'Officer verified', count: m.approvedRecords, percent: base ? Math.min(100, m.approvedRecords / base * 100) : 0, color: 'bg-[var(--bd-success)]' },
  ]
  return <Panel eyebrow="Conversion path" title="Digitization progress" action={<span className="text-[10px] text-[var(--bd-text-subtle)]">From uploaded sources</span>}>
    {base === 0 ? <Empty title="No documents in the pipeline" detail="Progress will be measured against uploaded documents once intake begins." /> : <div className="space-y-5 px-5 py-5">{stages.map((item) => <div key={item.label}><div className="mb-1.5 flex justify-between gap-3 text-[11px]"><span className="font-medium text-[var(--bd-text-muted)]">{item.label}</span><strong className="tabular-nums text-[var(--bd-text)]">{formatCount(item.count)} <span className="font-medium text-[var(--bd-text-subtle)]">/ {formatCount(base)}</span></strong></div><div role="progressbar" aria-label={item.label} aria-valuenow={Math.round(item.percent)} aria-valuemin={0} aria-valuemax={100} className="h-2 overflow-hidden rounded-full bg-[#edf1ef]"><div className={`bd-dashboard-fill h-full rounded-full ${item.color}`} style={{ width: `${item.percent}%` }} /></div></div>)}<p className="border-t border-[var(--bd-border)] pt-3 text-[10px] leading-4 text-[var(--bd-text-subtle)]">Officer verification is a human decision. These figures count persisted prototype records.</p></div>}
  </Panel>
}

export function DashboardPage({ token, role = 'REVENUE_OFFICER', developmentData }: { token: string; role?: string; developmentData?: OperationsData }) {
  const reducedMotion = Boolean(useReducedMotion())
  const { state, retry } = useOperationsData(token, developmentData)
  const [animateMetrics, setAnimateMetrics] = useState(true)
  const refresh = () => { setAnimateMetrics(false); retry() }
  const canUpload = role === 'ADMIN' || role === 'REVENUE_OFFICER'
  const workspaceLabel = `${displayRoleName(role)} workspace`
  const workspaceDescription = role === 'ADMIN' ? 'Manage account access and oversee operational review and final decisions.' : role === 'REVENUE_OFFICER' ? 'Upload and process sources, correct fields, resolve findings, and make the final decision.' : role === 'VERIFIER' ? 'Review evidence, correct fields, resolve findings, and give a recommendation. Final decisions belong to a Revenue Officer or Administrator.' : 'Inspect evidence, review history, the audit trail, and GIS. Business data is read-only.'
  let currentWork = state.phase === 'loading' ? 'Loading current operational work…' : 'Current work is unavailable. Retry the data request below.'
  if (state.phase === 'ready') {
    const m = state.data.summary.metrics
    const openCases = `${formatCount(m.awaitingReview)} open review case${m.awaitingReview === 1 ? '' : 's'}`
    currentWork = role === 'AUDITOR'
      ? `${formatCount(m.recordsTotal)} structured record${m.recordsTotal === 1 ? '' : 's'} available for inspection; ${openCases}.`
      : role === 'VERIFIER'
        ? `${openCases} available for evidence review, correction, and recommendation.`
        : `${openCases}; ${formatCount(m.processingFailed)} failed source${m.processingFailed === 1 ? '' : 's'} need processing attention.`
    if (m.documentsTotal === 0) currentWork = canUpload ? 'No sources uploaded yet. Open Documents to begin intake.' : 'No sources uploaded yet. Work appears after a Revenue Officer or Administrator completes intake.'
  }
  return <div className="mx-auto w-full max-w-[1500px] space-y-4 pb-8 sm:space-y-5">
    <header className="flex flex-wrap items-end justify-between gap-4 pb-1"><div><p className="text-[10px] font-bold uppercase tracking-[.16em] text-[var(--bd-accent)]">{workspaceLabel}</p><h1 className="mt-1 text-[clamp(1.6rem,2.5vw,2.25rem)] font-semibold tracking-[-.045em] text-[var(--bd-text)]">BhuDrishti Command Center</h1><p className="mt-1 text-[13px] text-[var(--bd-text-muted)]">{workspaceDescription}</p></div><div className="flex items-center gap-2"><button type="button" onClick={refresh} className="inline-flex min-h-9 items-center gap-1.5 rounded-md border border-[var(--bd-border-strong)] bg-white px-3 text-xs font-semibold text-[var(--bd-text-muted)] hover:bg-[var(--bd-surface-muted)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--bd-info)]"><RefreshCw size={14} aria-hidden="true" />Refresh</button><a href={role === 'ADMIN' ? '#/settings' : role === 'VERIFIER' ? '#/review' : '#/documents'} className="inline-flex min-h-9 items-center gap-1.5 rounded-md bg-[var(--bd-accent)] px-3 text-xs font-semibold text-white hover:bg-[var(--bd-accent-hover)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--bd-info)]">{canUpload ? <Upload size={14} aria-hidden="true" /> : <FileText size={14} aria-hidden="true" />}{role === 'ADMIN' ? 'Manage access' : role === 'VERIFIER' ? 'Open review queue' : 'Open documents'}</a></div></header>
    <section className="bd-workspace-identity" aria-label="Your role and current work">
      <dl><div className="bd-workspace-role"><dt>Role</dt><dd>{displayRoleName(role)}</dd></div><div><dt>Responsibility</dt><dd>{workspaceDescription}</dd></div><div aria-live="polite"><dt>Current work</dt><dd>{currentWork}</dd><p>Shared operational dataset · not a personal assignment count</p></div></dl>
    </section>
    {state.phase === 'loading' && <div role="status" className="space-y-4"><p className="text-xs text-[var(--bd-text-muted)]">Loading persisted documents, review cases, and operational totals. This does not start document processing.</p><div className="h-12 rounded-xl bg-[#e9efec] motion-safe:animate-pulse" /><div className="grid grid-cols-2 gap-3 lg:grid-cols-5">{Array.from({ length: 5 }, (_, index) => <div key={index} className="h-32 rounded-xl bg-[#e9efec] motion-safe:animate-pulse" />)}</div><div className="h-56 rounded-xl bg-[#e9efec] motion-safe:animate-pulse" /></div>}
    {state.phase === 'error' && <div role="alert" className="rounded-xl border border-[#edceca] bg-[#fff8f6] p-6"><p className="flex items-center gap-2 font-semibold text-[var(--bd-danger)]"><CircleAlert size={18} aria-hidden="true" />Command Center data unavailable</p><p className="mt-2 text-sm text-[var(--bd-text-muted)]">{state.error}</p><button type="button" onClick={refresh} className="mt-4 inline-flex items-center gap-1.5 rounded-md bg-[var(--bd-accent)] px-3 py-2 text-xs font-semibold text-white"><RefreshCw size={13} aria-hidden="true" />Retry</button></div>}
    {state.phase === 'ready' && <><div className="flex flex-wrap items-center gap-2 rounded-lg border border-[#d6e5df] bg-[#f1f7f3] px-3.5 py-2.5 text-[11px] leading-4 text-[#3f6b59]" role="note"><ShieldCheck size={16} className="shrink-0" aria-hidden="true" /><span><strong>Prototype operations.</strong> {state.data.summary.disclaimer}</span></div><div><h2 className="mb-2 text-xs font-semibold text-[var(--bd-text)]">Operational priorities</h2><OverviewMetrics summary={state.data.summary} role={role} animate={animateMetrics} /></div><div className="grid min-w-0 items-start gap-4 xl:grid-cols-2"><ReviewQueue items={state.data.reviews} /><RecentDocuments items={state.data.documents} canUpload={canUpload} /></div><div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(290px,0.85fr)]"><VolumeChart summary={state.data.summary} reducedMotion={reducedMotion || !animateMetrics} /><ValidationMix summary={state.data.summary} /></div><div className="grid min-w-0 items-start gap-4 md:grid-cols-2 xl:grid-cols-3"><RecentActivity items={state.data.summary.recentActivity} role={role} /><SystemHealth failed={state.data.summary.metrics.processingFailed} /><DigitizationProgress summary={state.data.summary} /></div></>}
    <p className="flex flex-wrap items-center gap-2 border-t border-[var(--bd-border)] pt-4 text-[10px] text-[var(--bd-text-subtle)]"><Clock3 size={13} aria-hidden="true" />OCR reads the source. Rules extract and validate. A Verifier may recommend. A Revenue Officer or Administrator makes the final decision.</p>
  </div>
}
