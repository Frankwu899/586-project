import { useState } from 'react';
import type { CreativeDirection, TaskState } from './generated/contracts';
import { Badge, Field, type Mutate } from './ui';

function DirectionCard({ direction, selected, onSelect, state, mutate, busy, m2Blocked }: {
  direction: CreativeDirection; selected: boolean; onSelect: () => void; state: TaskState; mutate: Mutate; busy: boolean; m2Blocked: boolean;
}) {
  const [fields, setFields] = useState({ core_message: direction.core_message, hook: direction.hook, narrative: direction.narrative, cta: direction.cta });
  const [instruction, setInstruction] = useState('');
  const dirty = (Object.keys(fields) as (keyof typeof fields)[]).some((key) => fields[key] !== direction[key]);
  const current = direction.currentness === 'current';
  const inputs = { brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis, direction_revision: direction.revision };
  return <article className={`direction${selected ? ' selected' : ''}`} aria-label={`Direction ${direction.direction_id}`}>
    <label className="select-choice"><input type="radio" name="direction" checked={selected} onChange={onSelect} disabled={busy || !current} />Select this direction</label>
    <p><Badge warning={!current}>{direction.currentness}</Badge><Badge warning={direction.approval_status === 'draft'}>{direction.approval_status}</Badge><small>revision {direction.revision} · {direction.origin.kind}</small></p>
    <form onSubmit={async (event) => { event.preventDefault(); await mutate(`/directions/${direction.direction_id}/edit`, { direction_revision: direction.revision, fields }); }}>
      <fieldset disabled={busy || !current}>
        <Field label="Core message"><textarea required value={fields.core_message} onChange={(event) => setFields({ ...fields, core_message: event.target.value })} /></Field>
        <Field label="Hook"><textarea required value={fields.hook} onChange={(event) => setFields({ ...fields, hook: event.target.value })} /></Field>
        <Field label="Narrative"><textarea required value={fields.narrative} onChange={(event) => setFields({ ...fields, narrative: event.target.value })} /></Field>
        <Field label="CTA"><textarea required value={fields.cta} onChange={(event) => setFields({ ...fields, cta: event.target.value })} /></Field>
        <button type="submit" className="secondary" disabled={!dirty}>Save direction edits</button>
      </fieldset>
    </form>
    <h4>Production implications</h4><ul>{direction.production_requirements.map((item, index) => <li key={index}>{item}</li>)}</ul>
    <p>{direction.rationale}</p>
    <h4>Hypotheses to test</h4><ul>{direction.hypotheses.map((item, index) => <li key={index}>{item}</li>)}</ul>
    <details><summary>Evidence and production notes</summary>
      <ul>{direction.evidence.map((item, index) => <li key={index}>{item.event_id} · analysis revision {item.analysis_revision}: {item.reason}</li>)}</ul>
      {direction.production_notes.map((item, index) => <p key={index}>{item}</p>)}
      <small>Uses brand/task brief revision {direction.brief_ref.revision} and reviewed analysis revision {direction.analysis_ref.revision}.</small>
    </details>
    <form onSubmit={async (event) => { event.preventDefault(); if (await mutate(`/directions/${direction.direction_id}/refine`, { ...inputs, instruction })) setInstruction(''); }}>
      <fieldset disabled={busy || m2Blocked || !current || dirty}>
        <Field label="Refinement instruction" hint={state.task.mode === 'sample' ? 'Sample demonstration: “make it presenter-free”. Other instructions are saved as production notes and marked not interpreted.' : 'Describe the changes you want. A refined draft requires your approval again.'}><textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Make it presenter-free" required /></Field>
        <button type="submit" disabled={!instruction.trim()}>Apply instruction</button>
      </fieldset>
    </form>
    <div className="actions"><button type="button" disabled={busy || m2Blocked || !selected || !current || dirty || direction.approval_status === 'approved'} onClick={() => mutate(`/directions/${direction.direction_id}/approve`, inputs)}>Approve this direction</button></div>
    {dirty && <p className="muted">Save field edits before applying instructions or approving.</p>}
  </article>;
}

export default function Directions({ state, mutate, busy, m2Blocked }: { state: TaskState; mutate: Mutate; busy: boolean; m2Blocked: boolean }) {
  const latest = Array.from(new Map(state.directions.map((direction) => [direction.direction_id, direction])).values());
  const current = latest.filter((direction) => direction.currentness === 'current');
  const choices = current.length ? current : latest.slice(-2);
  const selected = state.task.chosen_direction?.id ?? '';
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  const video = state.videos.find((item) => item.video_id === analysis?.video_id);
  const ready = Boolean(state.task.current_brief && analysis?.review.user_confirmed && analysis.status === 'succeeded' && analysis.frame_count !== null && video?.frame_timing);
  return <section id="directions" className="panel" aria-labelledby="directions-heading">
    <h2 id="directions-heading">4. Compare and approve a direction</h2>
    <p className="muted">Two {state.task.mode === 'sample' ? 'sample ' : ''}drafts use your brief and reviewed evidence. Edits and applied refinements require approval again. Intended benefits are hypotheses.</p>
    <button type="button" disabled={busy || m2Blocked || !ready} onClick={() => mutate('/directions/generate', { brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis })}>Generate two {state.directions.length ? 'new ' : ''}{state.task.mode === 'sample' ? 'sample ' : ''}directions</button>
    {!ready && <p className="muted">Apply your inputs and confirm a successful current analysis first.</p>}
    {choices.length > 0 && <div className="grid" style={{ marginTop: '1rem' }}>{choices.map((direction) => <DirectionCard key={`${direction.direction_id}:${direction.revision}`} direction={direction} selected={selected === direction.direction_id} onSelect={() => { void mutate(`/directions/${direction.direction_id}/select`, { direction_revision: direction.revision }); }} state={state} mutate={mutate} busy={busy} m2Blocked={m2Blocked} />)}</div>}
    {state.feedback.length > 0 && <details open><summary>Saved refinement instructions ({state.feedback.length})</summary>{state.feedback.map((feedback) => <div key={feedback.feedback_id}>
      <p><strong>{feedback.instruction}</strong> <Badge warning={feedback.status !== 'applied'}>{feedback.status.replaceAll('_', ' ')}</Badge></p>
      <p>{feedback.explanation}</p><small>Target direction revision {feedback.target_direction.revision}{feedback.resulting_direction ? ` → draft revision ${feedback.resulting_direction.revision}; approval required.` : ''}</small>
    </div>)}</details>}
  </section>;
}
