import { useEffect, useState } from 'react'
import { enrollVoice, listVoiceProfiles, type SpeakerVoiceProfile } from '../api'

type Props = {
  voiceId: string
  onVoiceIdChange: (voiceId: string) => void
}

export default function VoiceProfilePanel({ voiceId, onVoiceIdChange }: Props) {
  const [voiceName, setVoiceName] = useState('')
  const [description, setDescription] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [consent, setConsent] = useState(false)
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [profiles, setProfiles] = useState<SpeakerVoiceProfile[]>([])

  useEffect(() => {
    refreshProfiles()
  }, [])

  async function refreshProfiles() {
    try {
      const savedProfiles = await listVoiceProfiles()
      setProfiles(savedProfiles)
    } catch {
      setProfiles([])
    }
  }

  async function handleEnroll() {
    setMessage(null)
    if (!voiceName.trim()) {
      setMessage('Add a speaker name before enrolling.')
      return
    }
    if (files.length === 0) {
      setMessage('Add at least one clean voice sample.')
      return
    }
    if (!consent) {
      setMessage('Consent is required before creating a voice clone.')
      return
    }

    setStatus('saving')
    try {
      const response = await enrollVoice(voiceName, files, consent, description)
      onVoiceIdChange(response.voice_id)
      await refreshProfiles()
      setStatus('saved')
      setMessage(`${response.voice_name} is selected for the next translation.`)
    } catch (error) {
      setStatus('error')
      setMessage(error instanceof Error ? error.message : 'Voice enrollment failed.')
    }
  }

  return (
    <section className="voice-panel">
      <div className="voice-panel-head">
        <strong>Speaker voice</strong>
        {voiceId && <span>Selected</span>}
      </div>

      <label className="field">
        <span>Saved speaker profiles</span>
        <select
          value={voiceId}
          onChange={(event) => onVoiceIdChange(event.target.value)}
        >
          <option value="">Use default voice from backend</option>
          {profiles.map((profile) => (
            <option key={profile.id} value={profile.voice_id}>
              {profile.voice_name} ({profile.provider})
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Manual voice ID</span>
        <input
          value={voiceId}
          placeholder="Paste ElevenLabs voice ID"
          onChange={(event) => onVoiceIdChange(event.target.value)}
        />
      </label>
      {voiceId.startsWith('demo-') && (
        <p className="voice-message error">
          Demo voice IDs only work in demo mode. Use a real ElevenLabs voice ID for live translations.
        </p>
      )}

      <div className="divider" />

      <label className="field">
        <span>New speaker name</span>
        <input
          value={voiceName}
          placeholder="Example: Priya voice"
          onChange={(event) => setVoiceName(event.target.value)}
        />
      </label>

      <label className="field">
        <span>Voice samples</span>
        <input
          type="file"
          multiple
          accept="audio/webm,audio/wav,audio/mpeg,audio/mp3,audio/mp4,audio/ogg,.webm,.wav,.mp3,.m4a,.ogg"
          onChange={(event) => setFiles(Array.from(event.target.files ?? []))}
        />
      </label>

      <label className="field">
        <span>Description</span>
        <textarea
          value={description}
          placeholder="Optional voice description"
          rows={3}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>

      <label className="consent compact">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>I confirm these samples are my own voice or I have explicit written permission to clone this voice.</span>
      </label>

      <button
        type="button"
        className="voice-enroll"
        disabled={status === 'saving'}
        onClick={handleEnroll}
      >
        {status === 'saving' ? 'Creating voice...' : 'Create voice from samples'}
      </button>

      {message && <p className={`voice-message ${status}`}>{message}</p>}
    </section>
  )
}
