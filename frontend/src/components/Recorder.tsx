import { useEffect, useRef, useState } from 'react'
import Waveform from './Waveform'

type Props = {
  onSubmit: (blob: Blob, consent: boolean) => void
  disabled: boolean
}

export default function Recorder({ onSubmit, disabled }: Props) {
  const [state, setState] = useState<'idle' | 'recording' | 'paused' | 'ready'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [consent, setConsent] = useState(false)
  const [level, setLevel] = useState(0.2)
  const [message, setMessage] = useState<string | null>(null)
  const [micPermission, setMicPermission] = useState<'unknown' | 'prompt' | 'granted' | 'denied' | 'unsupported'>('unknown')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const animationRef = useRef<number | null>(null)

  useEffect(() => {
    let timer: number | undefined
    if (state === 'recording') {
      timer = window.setInterval(() => setElapsed((value) => value + 1), 1000)
    }
    return () => window.clearInterval(timer)
  }, [state])

  useEffect(() => {
    checkMicPermission()
  }, [])

  async function checkMicPermission() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setMicPermission('unsupported')
      return
    }

    try {
      const permissions = navigator.permissions
      if (!permissions?.query) {
        setMicPermission('prompt')
        return
      }
      const status = await permissions.query({ name: 'microphone' as PermissionName })
      setMicPermission(status.state as 'prompt' | 'granted' | 'denied')
      status.onchange = () => setMicPermission(status.state as 'prompt' | 'granted' | 'denied')
    } catch {
      setMicPermission('prompt')
    }
  }

  async function requestMicAccess() {
    setMessage(null)
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission('unsupported')
      setMessage('This browser cannot show a microphone permission prompt. Try Chrome or Safari, or use the audio file picker.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach((track) => track.stop())
      setMicPermission('granted')
      setMessage('Microphone permission is enabled. You can start recording now.')
    } catch (error) {
      const name = error instanceof DOMException ? error.name : 'microphone_error'
      setMicPermission(name === 'NotAllowedError' || name === 'PermissionDeniedError' ? 'denied' : 'unknown')
      setMessage('Microphone permission was not granted. Allow microphone access for localhost in your browser settings, or upload an audio file below.')
    }
  }

  async function start() {
    setMessage(null)
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setMessage('This browser cannot access the microphone here. Use the audio file picker below, or open the app in Chrome or Safari.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      setMicPermission('granted')
      streamRef.current = stream
      chunksRef.current = []
      const mimeType = preferredMimeType()
      const options = mimeType ? { mimeType } : undefined
      const recorder = new MediaRecorder(stream, options)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const type = recorder.mimeType || 'audio/webm'
        const blob = new Blob(chunksRef.current, { type })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        setState('ready')
        stream.getTracks().forEach((track) => track.stop())
        if (animationRef.current) cancelAnimationFrame(animationRef.current)
      }
      recorder.start()
      setElapsed(0)
      setAudioBlob(null)
      setAudioUrl(null)
      setState('recording')
      monitorLevel(stream)
    } catch (error) {
      const name = error instanceof DOMException ? error.name : 'microphone_error'
      const denied = name === 'NotAllowedError' || name === 'PermissionDeniedError'
      if (denied) setMicPermission('denied')
      setMessage(
        denied
          ? 'Microphone permission was blocked. Allow microphone access for localhost, then try again, or upload an audio file below.'
          : `Microphone could not start (${name}). Try the audio file picker below.`
      )
    }
  }

  function monitorLevel(stream: MediaStream) {
    const context = new AudioContext()
    const source = context.createMediaStreamSource(stream)
    const analyser = context.createAnalyser()
    const data = new Uint8Array(analyser.frequencyBinCount)
    source.connect(analyser)
    const tick = () => {
      analyser.getByteFrequencyData(data)
      const avg = data.reduce((sum, value) => sum + value, 0) / data.length
      setLevel(Math.min(1, avg / 90))
      animationRef.current = requestAnimationFrame(tick)
    }
    tick()
  }

  function pause() {
    recorderRef.current?.pause()
    setState('paused')
  }

  function resume() {
    recorderRef.current?.resume()
    setState('recording')
  }

  function stop() {
    recorderRef.current?.stop()
  }

  function reset() {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    setState('idle')
    setElapsed(0)
    setAudioBlob(null)
    setMessage(null)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioUrl(null)
  }

  function chooseFile(file: File | undefined) {
    if (!file) return
    setMessage(null)
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    setAudioBlob(file)
    setAudioUrl(URL.createObjectURL(file))
    setElapsed(0)
    setState('ready')
  }

  function preferredMimeType(): string | undefined {
    const options = [
      'audio/mp4',
      'audio/webm;codecs=opus',
      'audio/webm',
      'audio/ogg;codecs=opus'
    ]
    return options.find((type) => MediaRecorder.isTypeSupported(type))
  }

  const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0')
  const seconds = (elapsed % 60).toString().padStart(2, '0')

  return (
    <section className="recorder">
      <div className="record-top">
        <div>
          <p className="eyebrow">Record English audio</p>
          <h2>{minutes}:{seconds}</h2>
        </div>
        <span className={`status ${state}`}>{state}</span>
      </div>

      <Waveform level={level} recording={state === 'recording'} />

      {state === 'idle' && (
        <div className={`permission-card ${micPermission}`}>
          <div>
            <strong>Microphone access</strong>
            <p>{permissionText(micPermission)}</p>
          </div>
          {micPermission !== 'granted' && micPermission !== 'unsupported' && (
            <button type="button" className="secondary" onClick={requestMicAccess}>
              Allow microphone
            </button>
          )}
        </div>
      )}

      <div className="controls">
        {state === 'idle' && <button onClick={start} disabled={disabled}>Start recording</button>}
        {state === 'recording' && (
          <>
            <button onClick={pause} className="secondary">Pause</button>
            <button onClick={stop}>Stop</button>
          </>
        )}
        {state === 'paused' && (
          <>
            <button onClick={resume}>Resume</button>
            <button onClick={stop} className="secondary">Stop</button>
          </>
        )}
        {state === 'ready' && (
          <>
            <button onClick={() => audioBlob && onSubmit(audioBlob, consent)} disabled={!consent || disabled}>
              Translate to Hindi
            </button>
            <button onClick={reset} className="secondary">Record again</button>
          </>
        )}
      </div>

      {message && <div className="recorder-message">{message}</div>}

      {state !== 'recording' && state !== 'paused' && (
        <label className="upload-fallback">
          <span>Or choose an audio file</span>
          <input
            type="file"
            accept="audio/webm,audio/wav,audio/mpeg,audio/mp3,audio/mp4,audio/ogg,.webm,.wav,.mp3,.m4a,.ogg"
            onChange={(event) => chooseFile(event.target.files?.[0])}
          />
        </label>
      )}

      {audioUrl && <audio src={audioUrl} controls className="player" />}

      <label className="consent">
        <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />
        <span>I confirm this is my own voice or I have explicit written permission to use this voice for AI translation.</span>
      </label>
    </section>
  )
}

function permissionText(permission: 'unknown' | 'prompt' | 'granted' | 'denied' | 'unsupported') {
  if (permission === 'granted') return 'Ready to record.'
  if (permission === 'denied') return 'Blocked. Enable microphone access for localhost in your browser settings.'
  if (permission === 'unsupported') return 'This browser cannot record audio here. Use the audio file picker instead.'
  return 'Click Allow microphone to trigger the browser permission prompt.'
}
