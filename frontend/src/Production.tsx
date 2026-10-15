import { useState } from 'react';
import type { ProductionCreativeBrief, TextStoryboard, TaskState, StoryboardRow } from './generated/contracts';
import { Badge, Field, lines, seconds, type Mutate } from './ui';

function OutputEditor({ brief, storyboard, mutate, busy }: { brief: ProductionCreativeBrief; storyboard: TextStoryboard; mutate: Mutate; busy: boolean }) {
  const [fields, setFields] = useState({ title: brief.title, core_message: brief.core_message, hook: brief.hook, narrative: brief.narrative, cta: brief.cta, production_notes: brief.production_notes.join('\n') });
  const [rows, setRows] = useState<StoryboardRow[]>(storyboard.rows);
  const setRow = (id: string, field: 'visual' | 'dialogue' | 'on_screen_text' | 'sound' | 'cta', value: string) => setRows((items) => items.map((row) => row.row_id === id ? { ...row, [field]: value } : row));
  return <form onSubmit={async (event) => {
    event.preventDefault();
    await mutate('/outputs/edit', { production_brief_ref: { id: brief.output_id, revision: brief.revision }, storyboard_ref: { id: storyboard.output_id, revision: storyboard.revision }, brief_fields: { ...fields, production_notes: lines(fields.production_notes) }, rows });
  }}>
    <fieldset disabled={busy}>
      <h3>Production creative brief</h3>
      <p><Badge warning={brief.currentness === 'outdated'}>{brief.currentness}</Badge><Badge warning>{brief.origin.kind} output</Badge>Revision {brief.revision}{brief.edited ? ' · manually edited' : ''}</p>
      <div className="grid">
        <Field label="Production title"><input required value={fields.title} onChange={(event) => setFields({ ...fields, title: event.target.value })} /></Field>
        <Field label="Production core message"><textarea required value={fields.core_message} onChange={(event) => setFields({ ...fields, core_message: event.target.value })} /></Field>
        <Field label="Production Hook"><textarea required value={fields.hook} onChange={(event) => setFields({ ...fields, hook: event.target.value })} /></Field>
        <Field label="Production narrative"><textarea required value={fields.narrative} onChange={(event) => setFields({ ...fields, narrative: event.target.value })} /></Field>
        <Field label="Production CTA"><textarea required value={fields.cta} onChange={(event) => setFields({ ...fields, cta: event.target.value })} /></Field>
        <Field label="Production notes" hint="One note per line."><textarea value={fields.production_notes} onChange={(event) => setFields({ ...fields, production_notes: event.target.value })} /></Field>
      </div>
      <h3>Text storyboard</h3>
      <p><Badge warning={storyboard.currentness === 'outdated'}>{storyboard.currentness}</Badge>Revision {storyboard.revision} · {seconds(storyboard.target_duration_seconds)} planned duration</p>
      <p className="muted">Times below belong to the planned new video. Reference evidence remains linked to its original analysis and source-video clock.</p>
      {rows.map((row, index) => <div className="story-row" key={row.row_id}>
        <h4>Shot {index + 1} · planned {seconds(row.start_seconds)}–{seconds(row.end_seconds)}</h4>
        <div className="grid">
          <Field label={`Shot ${index + 1} visuals`}><textarea required value={row.visual} onChange={(event) => setRow(row.row_id, 'visual', event.target.value)} /></Field>
          <Field label={`Shot ${index + 1} dialogue`}><textarea value={row.dialogue ?? ''} onChange={(event) => setRow(row.row_id, 'dialogue', event.target.value)} /></Field>
          <Field label={`Shot ${index + 1} on-screen text`}><textarea value={row.on_screen_text ?? ''} onChange={(event) => setRow(row.row_id, 'on_screen_text', event.target.value)} /></Field>
          <Field label={`Shot ${index + 1} sound`}><textarea value={row.sound ?? ''} onChange={(event) => setRow(row.row_id, 'sound', event.target.value)} /></Field>
          <Field label={`Shot ${index + 1} CTA`}><textarea value={row.cta ?? ''} onChange={(event) => setRow(row.row_id, 'cta', event.target.value)} /></Field>
        </div>
        <small>Reference evidence: {row.evidence.map((item) => `${item.event_id} (analysis r${item.analysis_revision})`).join(', ') || 'No reference citation'}</small>
      </div>)}
      <button type="submit">Save production edits</button>
    </fieldset>
  </form>;
}

export default function Production({ state, mutate, busy }: { state: TaskState; mutate: Mutate; busy: boolean }) {
  const brief = state.production_briefs.find((item) => item.output_id === state.task.current_production_brief?.id && item.revision === state.task.current_production_brief.revision);
  const storyboard = state.storyboards.find((item) => item.output_id === state.task.current_storyboard?.id && item.revision === state.task.current_storyboard.revision);
  const approved = state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision && item.approval_status === 'approved' && item.currentness === 'current');
  return <section className="panel" aria-labelledby="production-heading">
    <h2 id="production-heading">5. Production materials and exports</h2>
    <p className="muted">Generate from the exact approved direction. Regeneration creates a new saved output and preserves previous work in history.</p>
    <button type="button" disabled={busy || !approved} onClick={() => mutate('/outputs/generate', { direction_ref: state.task.selected_direction, brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis })}>{brief ? 'Regenerate production materials' : 'Generate production materials'}</button>
    {!approved && <p className="muted">Explicitly approve a current direction to generate production materials.</p>}
    {brief && storyboard && <>
      {brief.currentness === 'outdated' && <p className="notice">These outputs are outdated because an upstream input changed. Your saved work is preserved. Approve an updated direction before regenerating.</p>}
      <p className="muted">Sources: brand/task brief r{brief.brief_ref.revision}, analysis r{brief.analysis_ref.revision}, approved direction r{brief.direction_ref.revision}. {brief.origin.description}</p>
      <div className="actions"><a className="button" href={`/api/tasks/${state.task.task_id}/export/brief.md`} download>Export brief (Markdown)</a><a className="button" href={`/api/tasks/${state.task.task_id}/export/storyboard.csv`} download>Export storyboard (CSV)</a></div>
      <OutputEditor key={`${brief.output_id}:${brief.revision}:${storyboard.output_id}:${storyboard.revision}`} brief={brief} storyboard={storyboard} mutate={mutate} busy={busy} />
    </>}
  </section>;
}
