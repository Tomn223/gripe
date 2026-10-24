import { useEffect } from 'react'

function fmt(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

export default function PostsPanel({ panel, onClose }) {
  useEffect(() => {
    const k = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', k)
    return () => window.removeEventListener('keydown', k)
  }, [onClose])

  return (
    <div className="overlay" onClick={onClose}>
      <aside className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-head">
          <div>
            <h2>{panel.title}</h2>
            <div className="hint">{panel.subtitle}</div>
          </div>
          <button className="close" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>
        {panel.loading && <div className="shimmer">Loading posts…</div>}
        {panel.error && <div className="error">{panel.error}</div>}
        <ul className="posts">
          {panel.posts.map((p) => (
            <li key={p.id} className="post">
              <div className="post-gist">{p.gist}</div>
              <blockquote>{p.text}</blockquote>
              <div className="post-meta">
                <span className={`sent ${p.sentiment}`}>{p.sentiment}</span>
                {p.brand && p.brand !== 'none' && <span className="tag">{p.brand}</span>}
                <span>♥ {p.likes ?? 0}</span>
                <span>{fmt(p.created_at)}</span>
                <a href={p.url} target="_blank" rel="noreferrer">
                  @{p.username} on X ↗
                </a>
              </div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
