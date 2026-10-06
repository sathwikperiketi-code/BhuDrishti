import { Activity, LayoutGrid, Network } from 'lucide-react'

const destinations = [
  { href: '#overview', label: 'Overview', icon: LayoutGrid },
  { href: '#system', label: 'System status', icon: Activity },
  { href: '#architecture', label: 'Architecture', icon: Network },
]

type NavigationProps = { mobile?: boolean }

export function Navigation({ mobile = false }: NavigationProps) {
  return (
    <nav aria-label="Primary navigation" className={mobile ? 'mt-4 flex gap-1 overflow-x-auto border-t border-[#e3ebe8] pt-3' : ''}>
      {!mobile && <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.2em] text-[#759193]">Foundation</p>}
      <ul className={mobile ? 'flex min-w-max gap-1' : 'space-y-1'}>
        {destinations.map(({ href, label, icon: Icon }) => (
          <li key={href}>
            <a
              href={href}
              className={mobile
                ? 'inline-flex min-h-10 items-center gap-2 rounded-lg px-3 text-xs font-semibold text-[#45665f] hover:bg-[#eff5f2] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2d7565]'
                : 'flex min-h-11 items-center gap-3 rounded-lg px-3 text-[13px] font-medium text-[#b6cbca] hover:bg-white/10 hover:text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#a2d3b6]'}
            >
              <Icon className="h-4 w-4" strokeWidth={1.8} aria-hidden="true" />
              {label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
