type BrandProps = { compact?: boolean; iconOnly?: boolean }

export function Brand({ compact = false, iconOnly = false }: BrandProps) {
  return (
    <div className={`flex items-center gap-3 ${compact ? 'text-[#17313a]' : 'text-white'}`}>
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${compact ? 'bg-[#173c42]' : 'bg-[#29535a]'}`} aria-hidden="true">
        <svg width="25" height="25" viewBox="0 0 25 25" fill="none" aria-hidden="true">
          <path d="M3.5 5.5 11.5 2.5 21.5 5.5V19.5L13.5 22.5 3.5 19.5V5.5Z" stroke="#D5EBDB" strokeWidth="1.5" />
          <path d="M11.5 2.5V16.5M3.5 10.5 13.5 13.5 21.5 10.5M13.5 13.5V22.5" stroke="#D5EBDB" strokeWidth="1.3" />
          <circle cx="11.5" cy="16.5" r="2" fill="#A4D2B5" />
        </svg>
      </div>
      {!iconOnly && <div className="leading-tight">
        <div className="text-[18px] font-semibold tracking-[-0.04em]">BhuDrishti <span className="text-[#73b294]">AI</span></div>
        <div className={`mt-0.5 text-[10px] font-semibold uppercase tracking-[0.19em] ${compact ? 'text-[#76928b]' : 'text-[#a4bbb9]'}`}>Record intelligence</div>
      </div>}
    </div>
  )
}
