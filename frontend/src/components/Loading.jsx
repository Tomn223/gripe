import Logo from './Logo'

export default function Loading({ topic, stages, onCancel }) {
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
        <button className="link" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </main>
  )
}
