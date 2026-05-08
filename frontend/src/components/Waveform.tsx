type Props = {
  level: number
  recording: boolean
}

export default function Waveform({ level, recording }: Props) {
  const bars = Array.from({ length: 28 }, (_, index) => {
    const shape = Math.sin(index * 0.75) * 0.35 + 0.65
    const height = recording ? Math.max(8, level * 80 * shape) : 10 + shape * 18
    return <i key={index} style={{ height: `${height}px` }} />
  })

  return <div className={`waveform ${recording ? 'active' : ''}`}>{bars}</div>
}
