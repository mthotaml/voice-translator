export type TargetAudience =
  | 'gym_goers'
  | 'runners'
  | 'yoga_pilates'
  | 'crossfit'
  | 'tennis'
  | 'hikers'
  | 'middle_aged_wellness'
  | 'seniors'
  | 'families'

export type ProductFocus =
  | 'smoothies'
  | 'acai_bowls'
  | 'cold_pressed_juices'
  | 'fruits'
  | 'vegetables'
  | 'superfoods'
  | 'low_sugar'

export type CampaignCreate = {
  businessName: string
  locationName?: string
  neighborhood?: string
  goal?: string
  targetAudience: TargetAudience[]
  videoLengthSeconds: 15 | 30 | 45 | 60
  format: 'vertical_9_16' | 'square_1_1' | 'horizontal_16_9'
  tone: 'energetic' | 'premium' | 'calm' | 'educational' | 'inspirational'
  productFocus: ProductFocus[]
  cta?: string
  musicStyle: string
  voiceId?: string
  narrationScript?: string
}

export type AutoCampaignCreate = CampaignCreate & {
  folderPath?: string
}

export type MediaAnalysis = {
  detectedObjects: string[]
  detectedFoods: string[]
  setting: string
  mood: string
  vibe: string
  lighting: string
  backgroundDescription: string
  localContextSignals: string[]
  fitnessSignals: string[]
  wellnessSignals: string[]
  brandSafetyFlags: string[]
  qualityScore: number
  recommendedUse: string
  suggestedCaptionText: string
}

export type CampaignAsset = {
  id: string
  campaignId: string
  type: 'image' | 'video'
  url: string
  filename: string
  width?: number | null
  height?: number | null
  orientation?: string
  formatFit?: string[]
  skipReason?: string | null
  analysis?: MediaAnalysis | null
  qualityScore?: number | null
  createdAt: string
}

export type MusicTrack = {
  id: string
  title: string
  file: string
  energy: string
  bpm?: number | null
  mood: string[]
  license: string
  defaultVolume: number
  duckedVolume: number
  matchTheme?: string | null
  matchReason?: string | null
}

export type Scene = {
  index: number
  startTime: number
  endTime: number
  assetIds: string[]
  visualDirection: string
  onScreenText: string
  voiceoverLine: string
  transition: string
}

export type Caption = {
  startTime: number
  endTime: number
  text: string
}

export type Storyboard = {
  campaignId: string
  totalDurationSeconds: number
  scenes: Scene[]
  voiceoverScript: string
  captions: Caption[]
  musicStyle: string
  voiceTone: string
  voiceRecommendation: string
  musicRationale: string
  complianceNotes: string[]
  cta: string
  qualityScore: number
}

export type Campaign = {
  id: string
  name: string
  businessName: string
  locationName?: string | null
  neighborhood?: string | null
  goal?: string | null
  targetAudience: TargetAudience[]
  videoLengthSeconds: 15 | 30 | 45 | 60
  format: 'vertical_9_16' | 'square_1_1' | 'horizontal_16_9'
  tone: CampaignCreate['tone']
  productFocus: ProductFocus[]
  cta?: string | null
  status: 'draft' | 'analyzing' | 'script_ready' | 'rendering' | 'complete' | 'failed'
  musicStyle: string
  voiceId?: string | null
  narrationScript?: string | null
  createdAt: string
  updatedAt: string
  assets: CampaignAsset[]
  brief?: {
    campaignAngle: string
    targetAudienceSummary: string
    primaryMessage: string
    secondaryMessages: string[]
    visualStrategy: string
    hookOptions: string[]
    ctaOptions: string[]
    riskNotes: string[]
  } | null
  storyboard?: Storyboard | null
  compliance?: {
    approved: boolean
    issues: string[]
    rewrittenScript: string
    rewrittenCaptions: string[]
    notes: string[]
  } | null
  socialCaption?: {
    shortCaption: string
    longerCaption: string
    hashtags: string[]
  } | null
  musicTrack?: MusicTrack | null
  narrationUrl?: string | null
  renderUrl?: string | null
}

export type HealthResponse = {
  status: string
  version: string
  demo_mode: boolean
}

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

export type VoiceEnrollmentResponse = {
  voice_id: string
  voice_name: string
  provider: string
  created_at: string
  requires_verification?: boolean | null
}

export type SpeakerVoiceProfile = {
  id: number
  voice_id: string
  voice_name: string
  provider: string
  description?: string | null
  consent_confirmed: boolean
  created_at: string
  last_used_at?: string | null
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const CAMPAIGN_REQUEST_TIMEOUT_MS = 45_000

export const defaultGoal =
  'Create a compelling hyperlocal wellness video that promotes health and well-being through natural, nutrient-rich food and drinks such as smoothies, acai bowls, fruits, vegetables, cold-pressed juices, and superfoods. Emphasize active lifestyles, post-workout refueling, clean nutrition choices, and daily wellness without making unsupported medical claims.'

export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE}/api/health`)
  if (!response.ok) throw new Error('Backend is not responding')
  return response.json()
}

export async function createCampaign(payload: CampaignCreate): Promise<Campaign> {
  return jsonFetch('/api/campaigns', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export async function createAutoCampaignFromFolder(payload: AutoCampaignCreate): Promise<Campaign> {
  return jsonFetch('/api/campaigns/auto-folder', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export async function uploadAssets(campaignId: string, files: File[]): Promise<Campaign> {
  const form = new FormData()
  files.forEach((file) => form.append('files', file, file.name))
  return jsonFetch(`/api/campaigns/${campaignId}/assets`, { method: 'POST', body: form })
}

export async function addFolderAssets(campaignId: string, payload: AutoCampaignCreate): Promise<Campaign> {
  return jsonFetch(`/api/campaigns/${campaignId}/folder-assets`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload)
  })
}

export async function analyzeCampaign(campaignId: string): Promise<Campaign> {
  return jsonFetch(`/api/campaigns/${campaignId}/analyze`, { method: 'POST' })
}

export async function generateStoryboard(campaignId: string): Promise<Campaign> {
  return jsonFetch(`/api/campaigns/${campaignId}/storyboard`, { method: 'POST' })
}

export async function runCompliance(campaignId: string): Promise<Campaign> {
  return jsonFetch(`/api/campaigns/${campaignId}/compliance`, { method: 'POST' })
}

export async function generateNarration(campaignId: string): Promise<Campaign> {
  return jsonFetch(`/api/campaigns/${campaignId}/narration`, { method: 'POST' })
}

export async function renderCampaign(campaignId: string): Promise<Campaign> {
  return jsonFetch(`/api/campaigns/${campaignId}/render`, { method: 'POST' })
}

export function mediaUrl(path?: string | null): string | undefined {
  if (!path) return undefined
  if (path.startsWith('http')) return path
  return `${API_BASE}${path}`
}

export function downloadUrl(campaignId: string): string {
  return `${API_BASE}/api/campaigns/${campaignId}/download`
}

export async function enrollVoice(
  voiceName: string,
  files: File[],
  consent: boolean,
  description?: string
): Promise<VoiceEnrollmentResponse> {
  const form = new FormData()
  form.append('voice_name', voiceName)
  form.append('consent_confirmed', String(consent))
  if (description?.trim()) form.append('description', description.trim())
  files.forEach((file) => form.append('audio_samples', file, file.name))
  const response = await fetch(`${API_BASE}/api/voices/enroll`, { method: 'POST', body: form })
  const payload = await response.json()
  if (!response.ok) throw new Error(payload.message || payload.reason || 'Voice enrollment failed')
  return payload
}

export async function listVoiceProfiles(): Promise<SpeakerVoiceProfile[]> {
  const response = await fetch(`${API_BASE}/api/voices`)
  if (!response.ok) throw new Error('Could not load speaker voices')
  return response.json()
}

export async function downloadMedia(path: string, filename: string) {
  const url = mediaUrl(path)
  if (!url) return
  const response = await fetch(url)
  if (!response.ok) throw new Error('Media file is not available yet')
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

async function jsonFetch(path: string, options: RequestInit): Promise<Campaign> {
  const controller = new AbortController()
  const timer = window.setTimeout(() => controller.abort(), CAMPAIGN_REQUEST_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, { ...options, signal: controller.signal })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new Error('This step took too long, so the app stopped waiting. Try automatic folder mode for a faster build.')
    }
    throw error
  } finally {
    window.clearTimeout(timer)
  }
  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(payload?.detail || payload?.message || 'The campaign request failed')
  }
  return payload
}
