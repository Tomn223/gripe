import { useEffect, useState } from 'react'
import { api } from '../api'
import Logo from './Logo'

export default function Landing({ onSubmit, examples, error }) {
  const [value, setValue] = useState('')
  const [cached, setCached] = useState(examples)

  useEffect(() => {
    // Chips = markets already in the backend cache (instant); fall back to the built-in examples.
    api
      .topics()
      .then((ts) => {
        const names = ts.map((t) => t.topic)
        if (!names.length) return
        const ordered = [...examples.filter((e) => names.includes(e)), ...names.filter((n) => !examples.includes(n))]
        setCached(ordered.slice(0, 6))
      })
      .catch(() => {})
  }, [examples])

  return (
    <main className="landing">
      <div className="landing-inner">
        <Logo size={44} />
        <div className="landing-copy">
          <h1 className="landing-title">Find what’s broken in any market.</h1>
          <p className="landing-sub">
            Gripe reads thousands of real X posts and ranks what people are frustrated with, so you can spot where to build.
          </p>
        </div>
        <div className="landing-form">
          <form
            className="big-input"
            onSubmit={(e) => {
              e.preventDefault()
              onSubmit(value)
            }}
          >
            <input
              id="market"
              autoFocus
              value={value}
              onChange={(e) => setValue(e.target.value)}
              aria-label="Market"
              placeholder="What market are you exploring?"
            />
            <button type="submit" disabled={!value.trim()}>
              Find the gripes <span aria-hidden>→</span>
            </button>
          </form>
          <div className="try-row">
            {cached.map((x) => (
              <button key={x} className="chip chip-instant" onClick={() => onSubmit(x)} title="Cached, loads instantly">
                <span className="bolt" aria-hidden>⚡</span>
                {x}
              </button>
            ))}
          </div>
        </div>
        {error && <div className="error">{error}</div>}
        <ol className="steps">
          <li><b>1</b> Pull real posts</li>
          <li className="step-arrow" aria-hidden>→</li>
          <li><b>2</b> Grok filters the noise and groups themes</li>
          <li className="step-arrow" aria-hidden>→</li>
          <li><b>3</b> You see ranked pain points and opportunities</li>
        </ol>
      </div>
      <footer className="landing-foot">Built on real X posts, labeled by Grok.</footer>
    </main>
  )
}
