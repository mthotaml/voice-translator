export type VoiceProfile = {
  duration_seconds: number
  sample_rate?: number | null
  speech_rate_wpm?: number | null
  average_pitch_hz?: number | null
  pitch_range_hz?: number | null
  pitch_std_hz?: number | null
  rms_energy?: number | null
  peak_amplitude?: number | null
  silence_ratio?: number | null
  signal_to_noise_proxy?: number | null
  pause_count?: number | null
  average_pause_ms?: number | null
  longest_pause_ms?: number | null
  intensity_label: string
  cadence_label: string
  tone_label: string
  detected_mood: string
  mood_confidence: number
}

export type GuardrailResult = {
  allowed: boolean
  consent_verified: boolean
  content_safe: boolean
  impersonation_risk: string
  pii_detected: boolean
  warnings: string[]
  block_reason?: string | null
}

export type TranslationResponse = {
  request_id: string
  source_language: string
  target_language: string
  english_transcript: string
  hindi_translation: string
  detected_mood: string
  mood_confidence: number
  voice_profile: VoiceProfile
  tts_style_instructions: string
  audio_url?: string | null
  guardrails: GuardrailResult
}

export type HealthResponse = {
  status: string
  version: string
  demo_mode: boolean
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/api/health`)
  if (!response.ok) throw new Error('Backend is not responding')
  return response.json()
}

export async function translateVoice(audio: Blob, mood: string, consent: boolean): Promise<TranslationResponse> {
  const form = new FormData()
  const filename = audio instanceof File ? audio.name : `recording.${extensionForAudio(audio.type)}`
  form.append('audio', audio, filename)
  form.append('source_language', 'en-US')
  form.append('target_language', 'hi-IN')
  form.append('consent_confirmed', String(consent))
  if (mood !== 'auto') form.append('mood_override', mood)

  const response = await fetch(`${API_BASE}/api/translate/voice`, {
    method: 'POST',
    body: form
  })
  const payload = await response.json()
  if (!response.ok) {
    throw new Error(payload.message || payload.reason || 'Translation failed')
  }
  return payload
}

function extensionForAudio(mimeType: string): string {
  const cleanType = mimeType.split(';')[0].toLowerCase()
  if (cleanType.includes('wav')) return 'wav'
  if (cleanType.includes('mpeg') || cleanType.includes('mp3')) return 'mp3'
  if (cleanType.includes('mp4') || cleanType.includes('m4a')) return 'm4a'
  if (cleanType.includes('ogg')) return 'ogg'
  if (cleanType.includes('webm')) return 'webm'
  return 'webm'
}

export function mediaUrl(path?: string | null): string | undefined {
  if (!path) return undefined
  if (path.startsWith('http')) return path
  return `${API_BASE}${path}`
}

export async function downloadMedia(path: string, filename: string) {
  const generatedPrefix = '/media/generated/'
  const directPath = path.startsWith(generatedPrefix)
    ? `/api/media/generated/${path.slice(generatedPrefix.length)}`
    : path
  const url = mediaUrl(directPath)
  if (!url) return
  const response = await fetch(url)
  if (!response.ok) throw new Error('Audio file is not available yet')
  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(objectUrl)
}
