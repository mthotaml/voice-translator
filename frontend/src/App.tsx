import { useEffect, useState } from 'react'
import { getHealth, translateVoice, type HealthResponse, type TranslationResponse } from './api'
import MoodSelector from './components/MoodSelector'
import Recorder from './components/Recorder'
import TranslationResult from './components/TranslationResult'

const steps = [
  'Uploading audio',
  'Transcribing speech',
  'Analyzing tone and mood',
  'Translating to Hindi',
  'Generating your voice in Hindi',
  'Running safety checks'
]

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [mood, setMood] = useState('auto')
  const [status, setStatus] = useState<'idle' | 'processing' | 'complete' | 'error'>('idle')
  const [stepIndex, setStepIndex] = useState(0)
  const [result, setResult] = useState<TranslationResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    let timer: number | undefined
    if (status === 'processing') {
      timer = window.setInterval(() => {
        setStepIndex((value) => Math.min(value + 1, steps.length - 1))
      }, 850)
    }
    return () => window.clearInterval(timer)
  }, [status])

  async function handleSubmit(blob: Blob, consent: boolean) {
    setStatus('processing')
    setStepIndex(0)
    setError(null)
    setResult(null)
    try {
      const response = await translateVoice(blob, mood, consent)
      setResult(response)
      setStepIndex(steps.length - 1)
      setStatus('complete')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
      setStatus('error')
    }
  }

  return (
    <main className="shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">VoiceTranslate</p>
          <h1>English to Hindi voice translation that keeps the feeling intact.</h1>
          <p className="lede">
            Record your English voice, translate it into natural spoken Hindi, and preserve tone, cadence, and intent with consent-first guardrails.
          </p>
        </div>
        <div className="mode-card">
          <span>{health?.status === 'ok' ? 'Backend online' : 'Backend offline'}</span>
          {health?.demo_mode && <strong>DEMO MODE</strong>}
        </div>
      </header>

      <section className="workspace">
        <aside className="side-panel">
          <MoodSelector value={mood} onChange={setMood} />
          <div className="note">
            <strong>Privacy guardrails</strong>
            <p>Audio is temporary, consent is required, and generated speech includes a disclosure recommendation.</p>
          </div>
        </aside>

        <div className="main-panel">
          <Recorder onSubmit={handleSubmit} disabled={status === 'processing'} />

          {status === 'processing' && (
            <section className="pipeline">
              {steps.map((step, index) => (
                <div key={step} className={index <= stepIndex ? 'done' : ''}>
                  <span>{index < stepIndex ? '✓' : index === stepIndex ? '•' : ''}</span>
                  {step}
                </div>
              ))}
            </section>
          )}

          {status === 'error' && <div className="error">{error}</div>}
          {result && <TranslationResult result={result} />}
        </div>
      </section>
    </main>
  )
}
