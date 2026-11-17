export type SpeechModelId = 'whisper-1' | 'gpt-transcribe';
export const speechModelDescription = (model: SpeechModelId) => model === 'gpt-transcribe'
  ? 'GPT Transcribe returns text. Evidence uses the actual audio-chunk range; word and sentence timestamps are unavailable. Existing corrections remain protected.'
  : 'Whisper returns estimated segment timestamps. Verify wording and timing against the source.';

export default function SpeechModel({ id, value, onChange, disabled = false }: { id: string; value: SpeechModelId; onChange: (value: SpeechModelId) => void; disabled?: boolean }) {
  return <div className="va-speech-model"><label htmlFor={id}>Speech model</label><select id={id} value={value} disabled={disabled} aria-describedby={`${id}-description`} onChange={event => onChange(event.target.value as SpeechModelId)}><option value="whisper-1">Whisper · segment timestamps</option><option value="gpt-transcribe">GPT Transcribe · audio-chunk timing</option></select><p id={`${id}-description`} className="va-muted">{speechModelDescription(value)}</p></div>;
}
