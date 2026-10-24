import { useEffect, useState } from 'react'
import Logo from './Logo'

export default function Loading({ topic, stages, onCancel }) {
  const [secs, setSecs] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setSecs((x) => x + 1), 1000)
    return () => clearInterval(t)
  }, [])
  const elapsed = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
  const shown = stages.length
    ? stages
    : [{ key: 'pull', label: 'Pulling posts from X', status: 'running', detail: 'connecting…' }]
  return (
    <main className="loading">
      <div className="loading-card">
        <Logo size={30} />
        <h2>
          Listening to X about <em>{topic}</em>
        </h2>
        <ol className="stages">
          {shown.map((s) => (
            <li key={s.key} className={`stage ${s.status || 'pending'}`}>
              <span className="dot">{s.status === 'done' ? '✓' : ''}</span>
              <div className="stage-body">
                <div className="stage-label">
                  {s.label}
                  {s.count != null && s.status !== 'pending' && <span className="stage-count">{s.count}</span>}
                </div>
                {s.status !== 'pending' && s.detail && <div className="stage-detail">{s.detail}</div>}
              </div>
            </li>
          ))}
        </ol>
        <div className="stage-detail" style={{ textAlign: 'center', marginBottom: 8 }}>
          {elapsed} elapsed · Searching X usually takes 1–3 minutes, and the full analysis 2–4. Cached markets load instantly.
        </div>
        <button className="link" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </main>
  )
}
