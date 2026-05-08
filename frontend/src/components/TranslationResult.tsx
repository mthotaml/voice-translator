import { downloadMedia, mediaUrl, type TranslationResponse } from '../api'
import GuardrailPanel from './GuardrailPanel'
import { useState } from 'react'

export default function TranslationResult({ result }: { result: TranslationResponse }) {
  const audio = mediaUrl(result.audio_url)
  const confidence = Math.round(result.mood_confidence * 100)
  const isDemoAudio = result.guardrails.warnings.some((warning) => warning.includes('AI-generated'))
  const [downloadError, setDownloadError] = useState<string | null>(null)

  async function handleDownload() {
    if (!result.audio_url) return
    const extension = result.audio_url.split('.').pop() || 'wav'
    setDownloadError(null)
    try {
      await downloadMedia(result.audio_url, `hindi-translation-${result.request_id}.${extension}`)
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : 'Download failed. Open the audio file directly instead.')
    }
  }

  return (
    <section className="result">
      <div className="result-header">
        <div>
          <p className="eyebrow">Translation complete</p>
          <h2>{result.detected_mood.split('_').join(' ')} <span>{confidence}%</span></h2>
        </div>
        {audio && (
          <div className="download-actions">
            <button className="download" onClick={handleDownload}>Download audio</button>
            <a className="download secondary-link" href={audio} target="_blank" rel="noreferrer">Open audio file</a>
          </div>
        )}
      </div>

      {audio && <audio className="player" src={audio} controls />}
      {downloadError && <p className="download-error">{downloadError}</p>}
      {audio && isDemoAudio && (
        <p className="audio-note">
          Demo mode uses silent placeholder audio. Add OpenAI and ElevenLabs keys with DEMO_MODE=false to generate the Hindi voice audio.
        </p>
      )}

      <div className="copy-grid">
        <article>
          <h3>English transcript</h3>
          <p>{result.english_transcript}</p>
        </article>
        <article lang="hi">
          <h3>Hindi translation</h3>
          <p>{result.hindi_translation}</p>
        </article>
      </div>

      <details>
        <summary>Voice profile</summary>
        <dl className="profile">
          <div><dt>Duration</dt><dd>{result.voice_profile.duration_seconds}s</dd></div>
          <div><dt>Speech rate</dt><dd>{result.voice_profile.speech_rate_wpm ?? 'n/a'} wpm</dd></div>
          <div><dt>Pitch avg</dt><dd>{result.voice_profile.average_pitch_hz ?? 'n/a'} Hz</dd></div>
          <div><dt>Pitch range</dt><dd>{result.voice_profile.pitch_range_hz ?? 'n/a'} Hz</dd></div>
          <div><dt>Intensity</dt><dd>{result.voice_profile.intensity_label}</dd></div>
          <div><dt>Cadence</dt><dd>{result.voice_profile.cadence_label}</dd></div>
          <div><dt>Tone</dt><dd>{result.voice_profile.tone_label}</dd></div>
          <div><dt>Pauses</dt><dd>{result.voice_profile.pause_count ?? 0}</dd></div>
        </dl>
      </details>

      <GuardrailPanel guardrails={result.guardrails} />
    </section>
  )
}
