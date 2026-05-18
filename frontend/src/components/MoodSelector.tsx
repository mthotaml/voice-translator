type Props = {
  value: string
  onChange: (value: string) => void
}

const moods = [
  ['auto', 'Auto'],
  ['normal', 'Normal'],
  ['happy', 'Happy'],
  ['joyful', 'Joyful'],
  ['excited', 'Excited'],
  ['angry', 'Angry'],
  ['sad', 'Sad'],
  ['calm', 'Calm'],
  ['serious', 'Serious'],
  ['instructional', 'Instructional'],
  ['educational', 'Educational'],
  ['persuasive', 'Persuasive'],
  ['urgent', 'Urgent']
]

export default function MoodSelector({ value, onChange }: Props) {
  return (
    <label className="field">
      <span>Mood override</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {moods.map(([id, label]) => (
          <option key={id} value={id}>{label}</option>
        ))}
      </select>
    </label>
  )
}
