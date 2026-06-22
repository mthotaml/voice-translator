import { ChangeEvent, DragEvent, ReactNode, useEffect, useMemo, useState } from 'react'
import {
  addFolderAssets,
  analyzeCampaign,
  createAutoCampaignFromFolder,
  createCampaign,
  defaultGoal,
  downloadUrl,
  generateNarration,
  generateStoryboard,
  getHealth,
  mediaUrl,
  polishNarration,
  renderCampaign,
  runCompliance,
  uploadAssets,
  type Campaign,
  type CampaignCreate,
  type PolishNarrationResponse,
  type ProductFocus,
  type TargetAudience
} from './api'

const audienceOptions: Array<{ value: TargetAudience; label: string }> = [
  { value: 'gym_goers', label: 'Gym goers' },
  { value: 'runners', label: 'Runners' },
  { value: 'yoga_pilates', label: 'Yoga/Pilates' },
  { value: 'crossfit', label: 'CrossFit' },
  { value: 'tennis', label: 'Tennis' },
  { value: 'hikers', label: 'Hikers' },
  { value: 'middle_aged_wellness', label: 'Active adults' },
  { value: 'seniors', label: 'Seniors' },
  { value: 'families', label: 'Families' }
]

const productOptions: Array<{ value: ProductFocus; label: string }> = [
  { value: 'smoothies', label: 'Smoothies' },
  { value: 'acai_bowls', label: 'Acai bowls' },
  { value: 'cold_pressed_juices', label: 'Cold-pressed juices' },
  { value: 'fruits', label: 'Fruits' },
  { value: 'vegetables', label: 'Vegetables' },
  { value: 'superfoods', label: 'Superfoods' },
  { value: 'low_sugar', label: 'Low-sugar options' }
]

const steps = [
  'Create campaign',
  'Upload media',
  'Analyze assets',
  'Generate storyboard',
  'Compliance review',
  'Narration',
  'Render preview'
]

const PRODUCTION_DEADLINE_MS = 180_000

export default function App() {
  const [health, setHealth] = useState<string>('checking')
  const [campaign, setCampaign] = useState<Campaign | null>(null)
  const [files, setFiles] = useState<File[]>([])
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [folderPath, setFolderPath] = useState('/Users/mohan/Downloads/pure-greens-media')
  const [activeStep, setActiveStep] = useState(0)
  const [roughNarrationIdea, setRoughNarrationIdea] = useState('')
  const [polishedNarration, setPolishedNarration] = useState<PolishNarrationResponse | null>(null)
  const [form, setForm] = useState<CampaignCreate>({
    businessName: 'Pure Green',
    locationName: 'Irvine',
    neighborhood: 'Woodbridge',
    goal: defaultGoal,
    targetAudience: ['gym_goers', 'runners', 'yoga_pilates'],
    videoLengthSeconds: 30,
    format: 'vertical_9_16',
    tone: 'energetic',
    productFocus: ['smoothies', 'acai_bowls', 'cold_pressed_juices'],
    cta: 'Stop by Pure Green after your next workout.',
    musicStyle: 'Upbeat wellness pop',
    voiceId: '',
    narrationScript: ''
  })

  useEffect(() => {
    getHealth()
      .then((value) => setHealth(value.demo_mode ? 'Demo services online' : 'Live services online'))
      .catch(() => setHealth('Backend offline'))
  }, [])

  const selectedAsset = useMemo(() => campaign?.assets[0], [campaign])
  const downloadLink = campaign?.renderUrl ? downloadUrl(campaign.id) : ''

  async function runFullFlow() {
    setBusy('Building campaign')
    setError(null)
    const startedAt = Date.now()
    const checkDeadline = () => {
      if (Date.now() - startedAt > PRODUCTION_DEADLINE_MS) {
        throw new Error('The campaign build hit the 3 minute limit. Use automatic folder mode to finish faster with a quick media sample.')
      }
    }
    try {
      let current: Campaign

      if (files.length === 0) {
        setBusy('Selecting campaign folder assets')
        current = await createAutoCampaignFromFolder({ ...form, folderPath })
        setCampaign(current)
        setFiles([])
        setActiveStep(steps.length)
        return
      }

      current = await createCampaign(form)
      setCampaign(current)
      setActiveStep(1)
      checkDeadline()

      setBusy('Uploading selected media')
      current = await uploadAssets(current.id, files)
      setCampaign(current)
      setActiveStep(2)
      checkDeadline()

      if (files.length < 5) {
        setBusy('Adding folder backup assets')
        current = await addFolderAssets(current.id, { ...form, folderPath })
        setCampaign(current)
        checkDeadline()
      }

      setBusy('Selecting strongest assets')
      current = await analyzeCampaign(current.id)
      setCampaign(current)
      setActiveStep(3)
      checkDeadline()

      setBusy('Writing storyboard')
      current = await generateStoryboard(current.id)
      setCampaign(current)
      setActiveStep(4)
      checkDeadline()

      setBusy('Checking health claims')
      current = await runCompliance(current.id)
      setCampaign(current)
      setActiveStep(5)
      checkDeadline()

      setBusy('Creating narration')
      current = await generateNarration(current.id)
      setCampaign(current)
      setActiveStep(6)
      checkDeadline()

      setBusy('Rendering preview')
      current = await renderCampaign(current.id)
      setCampaign(current)
      setActiveStep(steps.length)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(null)
    }
  }

  function update<K extends keyof CampaignCreate>(key: K, value: CampaignCreate[K]) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function toggleAudience(value: TargetAudience) {
    setForm((current) => ({
      ...current,
      targetAudience: current.targetAudience.includes(value)
        ? current.targetAudience.filter((item) => item !== value)
        : [...current.targetAudience, value]
    }))
  }

  function toggleProduct(value: ProductFocus) {
    setForm((current) => ({
      ...current,
      productFocus: current.productFocus.includes(value)
        ? current.productFocus.filter((item) => item !== value)
        : [...current.productFocus, value]
    }))
  }

  function pickFiles(event: ChangeEvent<HTMLInputElement>) {
    setFiles(Array.from(event.target.files ?? []))
    setCampaign(null)
    setActiveStep(0)
  }

  function dropFiles(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setFiles(Array.from(event.dataTransfer.files ?? []))
    setCampaign(null)
    setActiveStep(0)
  }

  async function polishRoughNarration() {
    if (!roughNarrationIdea.trim()) {
      setError('Write a rough narration idea first, then polish it.')
      return
    }
    setBusy('Polishing narration')
    setError(null)
    try {
      const polished = await polishNarration({
        roughText: roughNarrationIdea,
        businessName: form.businessName,
        locationName: form.locationName,
        neighborhood: form.neighborhood,
        targetAudience: form.targetAudience,
        productFocus: form.productFocus,
        tone: form.tone,
        cta: form.cta,
        videoLengthSeconds: form.videoLengthSeconds
      })
      setPolishedNarration(polished)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not polish narration')
    } finally {
      setBusy(null)
    }
  }

  return (
    <main className="shell">
      <header className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Pure Green local studio</p>
          <h1>Build localized wellness video campaigns from store media.</h1>
          <p className="lede">
            Upload neighborhood photos or short clips, choose the audience and tone, then generate a safe storyboard, narration, captions, CTA, and media-matched render.
          </p>
        </div>
        <div className="status-panel">
          <span>{health}</span>
          <strong>{campaign?.status ?? 'Ready'}</strong>
        </div>
      </header>

      <section className="layout">
        <form className="builder" onSubmit={(event) => event.preventDefault()}>
          <Section title="Campaign Goal">
            <div className="grid two">
              <label className="field">
                Business
                <input value={form.businessName} onChange={(event) => update('businessName', event.target.value)} />
              </label>
              <label className="field">
                Location
                <input value={form.locationName} onChange={(event) => update('locationName', event.target.value)} />
              </label>
            </div>
            <label className="field">
              Neighborhood context
              <input value={form.neighborhood} onChange={(event) => update('neighborhood', event.target.value)} />
              <span className="field-hint">
                Helps localize the story and choose matching folder assets, such as Woodbridge, Downtown Irvine, near a gym, or close to a yoga studio.
              </span>
            </label>
            <label className="field">
              Goal
              <textarea rows={5} value={form.goal} onChange={(event) => update('goal', event.target.value)} />
            </label>
            <button className="secondary" type="button" onClick={() => update('goal', defaultGoal)}>
              Reset to default goal
            </button>
          </Section>

          <Section title="Audience">
            <ChipGroup options={audienceOptions} selected={form.targetAudience} onToggle={toggleAudience} />
          </Section>

          <Section title="Product Focus">
            <ChipGroup options={productOptions} selected={form.productFocus} onToggle={toggleProduct} />
          </Section>

          <Section title="Render Timing">
            <div className="auto-render-note">
              <strong>Auto render format</strong>
              <span>The app detects your uploaded media and picks phone, square, or web/iPad layout automatically. Campaign builds stop waiting after about 3 minutes so you are never stuck.</span>
              {campaign && <em>Selected: {formatLabel(campaign.format)}</em>}
            </div>
            <div className="grid four">
              {[15, 30, 45, 60].map((seconds) => (
                <Segment
                  key={seconds}
                  label={`${seconds}s`}
                  active={form.videoLengthSeconds === seconds}
                  onClick={() => update('videoLengthSeconds', seconds as CampaignCreate['videoLengthSeconds'])}
                />
              ))}
            </div>
          </Section>

          <Section title="Voice & Narration">
            <label className="field">
              ElevenLabs voice ID
              <input placeholder="Optional. Enter a voice ID to prioritize it." value={form.voiceId} onChange={(event) => update('voiceId', event.target.value)} />
              <span className="field-hint">Optional. If you leave this blank, the app chooses the best available voice for the campaign tone.</span>
            </label>
            <div className="narration-polisher">
              <label className="field">
                Rough campaign idea
                <textarea
                  rows={5}
                  placeholder="Write rough thoughts, favorite phrases, audience intent, or the feeling you want. Example: after yoga people should feel like Pure Green is the healthy local stop, fresh smoothies, not too salesy, upbeat."
                  value={roughNarrationIdea}
                  onChange={(event) => setRoughNarrationIdea(event.target.value)}
                />
                <span className="field-hint">ChatGPT turns this into polished ad narration. You can preview it, use it as-is, or edit it below.</span>
              </label>
              <button className="secondary" type="button" disabled={Boolean(busy)} onClick={polishRoughNarration}>
                Polish with ChatGPT
              </button>
              {polishedNarration && (
                <div className="polished-card">
                  <div className="polished-card-head">
                    <strong>Polished narration preview</strong>
                    <span>{polishedNarration.provider === 'openai' ? 'ChatGPT' : 'Demo polish'}</span>
                  </div>
                  <p>{polishedNarration.polishedNarration}</p>
                  {polishedNarration.onScreenText.length > 0 && (
                    <div className="screen-lines">
                      {polishedNarration.onScreenText.map((line) => (
                        <span key={line}>{line}</span>
                      ))}
                    </div>
                  )}
                  <em>{polishedNarration.rationale}</em>
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => update('narrationScript', polishedNarration.polishedNarration)}
                  >
                    Use this narration
                  </button>
                </div>
              )}
            </div>
            <label className="field">
              Narration text
              <textarea
                rows={6}
                placeholder="Optional. Write the exact voiceover here, or leave blank and the app will write it for you."
                value={form.narrationScript}
                onChange={(event) => update('narrationScript', event.target.value)}
              />
              <span className="field-hint">If provided, this becomes the voiceover. The app still checks it for safe wellness claims before generating audio.</span>
            </label>
          </Section>

          <Section title="Media">
            <label className="dropzone" onDragOver={(event) => event.preventDefault()} onDrop={dropFiles}>
              <input multiple type="file" accept="image/*,video/*" onChange={pickFiles} />
              <span>Upload photos or short videos</span>
              <strong>{files.length ? `${files.length} file${files.length === 1 ? '' : 's'} selected` : 'Choose media'}</strong>
            </label>
            {files.length > 0 && (
              <div className="file-list">
                {files.slice(0, 6).map((file) => (
                  <span key={file.name}>{file.name}</span>
                ))}
              </div>
            )}
            <label className="field folder-field">
              Backup campaign folder
              <input value={folderPath} onChange={(event) => setFolderPath(event.target.value)} />
            </label>
            <div className="auto-render-note">
              <strong>Automatic priority</strong>
              <span>Uploaded media and your voice ID are used first. If no media is uploaded, the app uses the campaign folder. If fewer than five files are uploaded, the app fills the rest from the folder automatically.</span>
            </div>
          </Section>

          <Section title="Style">
            <label className="field">
              Tone
              <select value={form.tone} onChange={(event) => update('tone', event.target.value as CampaignCreate['tone'])}>
                <option value="energetic">Energetic</option>
                <option value="premium">Premium</option>
                <option value="calm">Calm</option>
                <option value="educational">Educational</option>
                <option value="inspirational">Inspirational</option>
              </select>
              <span className="field-hint">Music is selected automatically from the campaign folder based on tone, audience, media energy, and product focus.</span>
            </label>
            <label className="field">
              Call to action
              <input value={form.cta} onChange={(event) => update('cta', event.target.value)} />
            </label>
          </Section>

          <button className="primary-action" type="button" disabled={Boolean(busy)} onClick={runFullFlow}>
            {busy ?? 'Generate campaign video'}
          </button>
          {error && <div className="error">{error}</div>}
        </form>

        <aside className="preview-column">
          {(busy || campaign) && (
            <section className="panel pipeline-panel">
              <div className="panel-head">
                <h2>Production Pipeline</h2>
                <span>{Math.min(activeStep, steps.length)}/{steps.length}</span>
              </div>
              <div className="timeline">
                {steps.map((step, index) => (
                  <div key={step} className={index < activeStep ? 'done' : index === activeStep ? 'active' : ''}>
                    <span>{index + 1}</span>
                    {step}
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className={`video-preview ${campaign?.format ?? form.format}`}>
            {selectedAsset?.type === 'image' ? (
              <img src={mediaUrl(selectedAsset.url)} alt="" />
            ) : selectedAsset?.type === 'video' ? (
              <video src={mediaUrl(selectedAsset.url)} muted autoPlay loop playsInline />
            ) : (
              <div className="preview-fill" />
            )}
            <div className="safe-frame">
              <span>{campaign?.storyboard?.captions[0]?.text ?? 'Refuel after movement'}</span>
              <strong>{form.businessName}</strong>
            </div>
          </section>

          {campaign?.renderUrl && (
            <section className="panel result-panel">
              <h2>Generated Video</h2>
              <p>Your campaign preview is ready. Follow the steps below to choose music, generate the video, and download it.</p>
              <iframe title="Generated campaign preview" src={downloadLink} />
            </section>
          )}
        </aside>
      </section>
    </main>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      {children}
    </section>
  )
}

function ChipGroup<T extends string>({
  options,
  selected,
  onToggle
}: {
  options: Array<{ value: T; label: string }>
  selected: T[]
  onToggle: (value: T) => void
}) {
  return (
    <div className="chips">
      {options.map((option) => (
        <button key={option.value} type="button" className={selected.includes(option.value) ? 'chip selected' : 'chip'} onClick={() => onToggle(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  )
}

function Segment({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button type="button" className={active ? 'segment active' : 'segment'} onClick={onClick}>
      {label}
    </button>
  )
}

function formatLabel(format: Campaign['format']): string {
  if (format === 'horizontal_16_9') return '16:9 web / iPad landscape'
  if (format === 'square_1_1') return '1:1 square social feed'
  return '9:16 phone / Reels / Shorts'
}
