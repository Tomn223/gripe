import { useState } from 'react'
import Logo from './Logo'

export default function Landing({ onSubmit, examples, error }) {
  const [value, setValue] = useState('')
  return (
    <main className="landing">
      <div className="landing-inner">
        <Logo size={44} />
        <h1 className="landing-title">What market are you thinking about entering?</h1>
        <form
          className="big-input"
          onSubmit={(e) => {
            e.preventDefault()
            onSubmit(value)
          }}
        >
          <input
            autoFocus
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="e.g. air fryers, dog harnesses, CRMs…"
            aria-label="Market"
          />
          <button type="submit" disabled={!value.trim()}>
            Find the gripes <span aria-hidden>→</span>
          </button>
        </form>
        <div className="chips">
          {examples.map((x) => (
            <button key={x} className="chip" onClick={() => onSubmit(x)}>
              {x}
            </button>
          ))}
        </div>
        {error && <div className="error">{error}</div>}
      </div>
    </main>
  )
}
