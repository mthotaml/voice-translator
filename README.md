# VoiceTranslate

VoiceTranslate is an emotion-preserving English to Hindi voice translator. It records English speech in the browser, transcribes it, estimates vocal mood and cadence, translates the content into natural spoken Hindi, and generates Hindi audio through a cloned voice provider.

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

MVP demo endpoint that validates consent and returns a demo voice ID. Production enrollment should call the ElevenLabs voice API and store consent records.

## Guardrails

- Consent is required before voice generation.
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
