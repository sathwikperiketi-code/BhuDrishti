import { ArrowRight, Database, Layers3, Monitor, Server } from 'lucide-react'

const layers = [
  { icon: Monitor, number: '01', title: 'Interface', detail: 'React shell, typed API client, accessible states', phase: 'Phase 1' },
  { icon: Server, number: '02', title: 'API layer', detail: 'FastAPI contracts and service boundaries', phase: 'Phase 1' },
  { icon: Layers3, number: '03', title: 'Domain services', detail: 'OCR, extraction, validation, review, GIS, audit', phase: 'Planned' },
  { icon: Database, number: '04', title: 'Data layer', detail: 'SQLite models and PostgreSQL-ready boundary', phase: 'Phase 1' },
]

export function ArchitecturePanel() {
  return (
    <div className="rounded-[18px] border border-[#dce6e2] bg-white p-5 shadow-[0_12px_35px_-34px_rgba(16,36,45,0.5)] sm:p-7">
      <ol aria-label="Target architecture layers" className="grid gap-3 xl:grid-cols-4">
        {layers.map(({ icon: Icon, number, title, detail, phase }, index) => (
          <li key={title} className="relative rounded-xl border border-[#e2ebe7] bg-[#fbfcfc] p-5">
            <div className="mb-8 flex items-start justify-between gap-2">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#eaf3ee] text-[#3b7d68]"><Icon className="h-[18px] w-[18px]" strokeWidth={1.8} aria-hidden="true" /></div>
              <span className="text-[10px] font-bold uppercase tracking-[0.13em] text-[#91a7a1]">{number} / {phase}</span>
            </div>
            <h3 className="text-sm font-semibold text-[#1d3b43]">{title}</h3>
            <p className="mt-1 text-xs leading-5 text-[#788d88]">{detail}</p>
            {index < layers.length - 1 && <ArrowRight className="absolute -right-[21px] top-1/2 z-10 hidden h-4 w-4 -translate-y-1/2 text-[#91aaa0] xl:block" aria-hidden="true" />}
          </li>
        ))}
      </ol>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#e6eeea] pt-5">
        <p className="text-xs leading-5 text-[#728781]">Contracts follow the backend OpenAPI schema. Later workflows will use the same service boundary.</p>
        <span className="rounded-full bg-[#edf5f0] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[#4d856d]">Human verification required</span>
      </div>
    </div>
  )
}
