# Pure Green Hyperlocal Video Studio

This repository now includes a working mock-first MVP for the **Pure Green Hyperlocal AI Video Marketing App** described in `../pure-green-build-spec.md`.

The app lets a local wellness brand create a campaign, upload store/neighborhood/product media, generate deterministic media analysis, produce a campaign brief, storyboard, captions, CTA, compliance-safe script, demo narration, social caption, and a downloadable render package. The current renderer is a placeholder manifest designed to be swapped for Remotion MP4 rendering.

## Pure Green MVP Flow

```text
Campaign setup
    |
    v
Media upload
    |
    v
Mock media analysis
    |
    v
Campaign brief + storyboard
    |
    v
Health-claim compliance rewrite
    |
    v
ElevenLabs narration or local demo audio fallback
    |
    v
Template preview + downloadable render package
```

## Pure Green Quick Start

Backend:

```bash
cd /Users/mohan/Documents/New\ project/voice-translator/backend
PYTHONPATH=. ./.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd /Users/mohan/Documents/New\ project/voice-translator/frontend
npm run dev -- --port 5173
```

If `5173` is busy, Vite will choose the next available port. Open the URL printed by Vite.

## Pure Green API

- `POST /api/campaigns`
- `POST /api/campaigns/{id}/assets`
- `POST /api/campaigns/{id}/analyze`
- `POST /api/campaigns/{id}/storyboard`
- `POST /api/campaigns/{id}/compliance`
- `POST /api/campaigns/{id}/narration`
- `POST /api/campaigns/{id}/render`
- `GET /api/campaigns/{id}`
- `GET /api/campaigns/{id}/download`
- `GET /api/music`

The compliance service rewrites unsupported health claims such as immunity, disease, guaranteed recovery, longevity, organic, non-GMO, gluten-free, zero-sugar, and similar unverified claims into safer lifestyle-oriented language.

## Approved Music Library

Put owned or properly licensed MP3 tracks in:

```bash
backend/media/music/
```

Then update:

```bash
backend/data/music_catalog.json
```

Each track should include an ID, title, file URL, energy, BPM, mood tags, license note, and volume settings:

```json
{
  "id": "energetic_wellness_pop",
  "title": "Energetic Wellness Pop",
  "file": "/media/music/energetic-wellness-pop.mp3",
  "energy": "high",
  "bpm": 118,
  "mood": ["fitness", "upbeat", "post-workout"],
  "license": "owned_or_licensed",
  "defaultVolume": 0.11,
  "duckedVolume": 0.035
}
```

The campaign generator automatically picks a track by visual/audience energy and mixes it quietly under narration in the browser preview export. Keep `duckedVolume` around `0.02-0.04` so music does not dominate the voiceover.

## Verification

```bash
cd backend
PYTHONPATH=. ./.venv/bin/pytest app/tests

cd ../frontend
npm run build
```

---

# VoiceTranslate

VoiceTranslate is an emotion-preserving English to Hindi voice translator. It records English speech in the browser, transcribes it, estimates vocal mood and cadence, translates the content into natural spoken Hindi, and generates Hindi audio through a cloned voice provider. Each speaker can use their own selected voice ID or enroll voice samples to create a new cloned voice.

The MVP is consent-first and demo-friendly: `DEMO_MODE=true` lets you test the complete browser flow without OpenAI or ElevenLabs keys.

## Architecture

```text
Browser Recorder
    |
    v
FastAPI /api/translate/voice
    |
    +--> Guardrails: consent, content safety, impersonation, PII warnings
    +--> Temp storage with retention cleanup
    +--> STT provider interface
    +--> Audio analysis and mood heuristics
    +--> Translation provider interface
    +--> TTS provider interface
    |
    v
Generated Hindi audio + structured JSON response
```

Project flow diagrams are included in `docs/`:

- `voice-translator-sequence-flow.pdf`
- `voice_translate_presentable_flow.pdf`

## Stack

- Frontend: React, TypeScript, Vite
- Backend: FastAPI, Python 3.11+
- Speech to text: OpenAI `gpt-4o-transcribe`
- Translation: OpenAI chat model
- Voice generation: ElevenLabs multilingual cloned voice TTS
- Audio analysis: `librosa`, `numpy`, `scipy`, `pydub`
- Storage: local temporary filesystem for MVP

## Quick Start

```bash
cd /Users/mohan/Documents/New\ project/voice-translator
cp .env.example .env
```

For a no-key local demo, keep `DEMO_MODE=true`.

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The default requirements intentionally skip heavy audio packages so the app runs cleanly on newer local Python versions. If you are on a brand-new Python release, the requirements allow newer compatible backend packages. For richer acoustic analysis, use Python 3.11 or 3.12 and install:

```bash
pip install -r requirements-audio.txt
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Docker

```bash
cd /Users/mohan/Documents/New\ project/voice-translator
cp .env.example .env
docker compose up --build
```

## Environment Variables

See `.env.example` for the complete list.

Important values:

- `DEMO_MODE=true`: skips external provider calls and returns mock transcript, Hindi translation, and generated sample audio.
- `OPENAI_API_KEY`: required when `DEMO_MODE=false` for transcription and translation.
- `ELEVENLABS_API_KEY`: required when `DEMO_MODE=false` for voice generation.
- `ELEVENLABS_VOICE_ID`: cloned voice ID used for Hindi speech generation.
- `AUDIO_RETENTION_MINUTES`: local cleanup window for uploaded and generated audio.

## ElevenLabs Voice Clone Setup

1. Record 5-10 minutes of clean single-speaker audio.
2. In ElevenLabs, create an Instant or Professional Voice Clone.
3. Confirm consent in ElevenLabs.
4. Copy the generated `voice_id`.
5. Put it in `.env` as `ELEVENLABS_VOICE_ID`.

Provider-specific note: the backend sends Hindi text to ElevenLabs using `eleven_multilingual_v2` with expressive voice settings. The route never exposes the API key to the browser.

## API

`GET /api/health`

Returns backend status, version, and demo mode.

`POST /api/translate/voice`

Multipart form fields:

- `audio`: WAV, WebM, MP3, M4A, or OGG file
- `source_language`: defaults to `en-US`
- `target_language`: defaults to `hi-IN`
- `mood_override`: optional mood label
- `voice_id`: optional provider voice ID override
- `consent_confirmed`: required boolean

The response includes transcript, Hindi translation, mood confidence, voice profile, generated audio URL, and guardrail status.

`POST /api/voices/enroll`

Enrolls a speaker voice. In demo mode, it validates consent and returns a demo voice ID. In real mode, it sends the uploaded samples to ElevenLabs Instant Voice Cloning and returns the new `voice_id`.

Multipart form fields:

- `voice_name`: label for this speaker voice
- `audio_samples`: one or more clean audio files
- `description`: optional voice description
- `consent_confirmed`: required boolean

The returned `voice_id` can be selected in the frontend and is passed into `/api/translate/voice` for that speaker's generated Hindi audio.

`GET /api/voices`

Returns saved local speaker profiles from SQLite. The frontend uses this to show the **Saved speaker profiles** dropdown. The local database stores speaker labels, provider, `voice_id`, consent status, and timestamps, but not raw voice sample audio.

## Guardrails

- Consent is required before voice generation.
- Consent is required before voice enrollment or cloning.
- Unsafe content and likely fraud or impersonation scripts are blocked.
- PII is warned about but not blocked.
- Low-quality audio returns warnings.
- Audio files are temporary and cleaned up after the configured retention window.
- The app recommends disclosure for generated translated voice audio.

This MVP does not use voice samples for model training.

## Tests

```bash
cd backend
pytest
```

The tests cover consent blocking, impersonation detection, PII warnings, audio validation, mood fallback behavior, and the demo translation contract.

## Known Limitations

- Mood detection is heuristic and probabilistic.
- Very short or noisy recordings reduce accuracy.
- Cross-language cloned voice quality depends on the TTS provider and clone quality.
- Some providers do not expose precise emotion controls.
- High-stakes public or commercial use needs stronger consent records, audit logs, watermarking, abuse monitoring, and legal review.

## Roadmap

- Voice enrollment with provider-backed clone creation
- Multiple language targets
- Streaming transcription and sentence-by-sentence generation
- Better emotion classifier using labeled audio
- S3/GCS storage, Postgres, authentication, and audit logs

## License

MIT for MVP.
