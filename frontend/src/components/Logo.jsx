export default function Logo({ size = 28, withText = true }) {
  return (
    <div className="logo" style={{ fontSize: size * 0.72 }}>
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
        <rect width="64" height="64" rx="16" fill="#ff5a36" />
        <path d="M18 22h28a4 4 0 0 1 4 4v14a4 4 0 0 1-4 4H30l-9 7v-7h-3a4 4 0 0 1-4-4V26a4 4 0 0 1 4-4z" fill="#fff" />
        <path d="M24 37c4-4 12-4 16 0" stroke="#ff5a36" strokeWidth="3.5" fill="none" strokeLinecap="round" />
        <circle cx="26" cy="30" r="2.4" fill="#ff5a36" />
        <circle cx="38" cy="30" r="2.4" fill="#ff5a36" />
      </svg>
      {withText && <span>Gripe</span>}
    </div>
  )
}
