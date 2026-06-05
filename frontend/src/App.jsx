import { useCallback, useEffect, useState } from 'react'
import './App.css'

function App() {
  const [health, setHealth] = useState(null)
  const [isChecking, setIsChecking] = useState(true)
  const [error, setError] = useState('')

  const fetchBackendHealth = async () => {
    const response = await fetch('/api/health')

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    return { ...data, checkedAt: new Date().toLocaleTimeString() }
  }

  const checkBackend = useCallback(async () => {
    setIsChecking(true)
    setError('')

    try {
      setHealth(await fetchBackendHealth())
    } catch (err) {
      setHealth(null)
      setError(err instanceof Error ? err.message : 'Unable to connect')
    } finally {
      setIsChecking(false)
    }
  }, [])

  useEffect(() => {
    let isCurrent = true

    fetchBackendHealth()
      .then((data) => {
        if (isCurrent) {
          setHealth(data)
        }
      })
      .catch((err) => {
        if (isCurrent) {
          setHealth(null)
          setError(err instanceof Error ? err.message : 'Unable to connect')
        }
      })
      .finally(() => {
        if (isCurrent) {
          setIsChecking(false)
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  const statusLabel = health?.status === 'ok' ? 'Connected' : 'Disconnected'

  return (
    <main className="app-shell">
      <section className="status-panel">
        <p className="eyebrow">OpenAI Codex Course</p>
        <h1>DB Agent Chat</h1>
        <p className="subtitle">React + Flask starter for the database agent system.</p>

        <div className={`status-card ${health?.status === 'ok' ? 'is-online' : 'is-offline'}`}>
          <span className="status-dot" aria-hidden="true" />
          <div>
            <p className="status-label">Backend Status</p>
            <strong>{isChecking ? 'Checking...' : statusLabel}</strong>
          </div>
        </div>

        <dl className="details">
          <div>
            <dt>Service</dt>
            <dd>{health?.service ?? '-'}</dd>
          </div>
          <div>
            <dt>Last Check</dt>
            <dd>{health?.checkedAt ?? '-'}</dd>
          </div>
          <div>
            <dt>Endpoint</dt>
            <dd>/api/health</dd>
          </div>
        </dl>

        {error ? <p className="error-message">Connection failed: {error}</p> : null}

        <button type="button" onClick={checkBackend} disabled={isChecking}>
          {isChecking ? 'Checking...' : 'Recheck backend'}
        </button>
      </section>
    </main>
  )
}

export default App
