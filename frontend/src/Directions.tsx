import { useEffect, useState } from 'react';
import type { CreativeDirection, TaskState } from './generated/contracts';
import { directionEvidence } from './directionPresentation';
import { useEditorDraft } from './useEditorDraft';
import { request } from './api';
import { Badge, Field, type Mutate } from './ui';
import './directions.css';

type DirectionFields = Pick<CreativeDirection, 'core_message' | 'hook' | 'narrative' | 'cta'>;
type GenerationLanguage = 'English' | 'Chinese';
type SeekEvidence = (frame: number) => void;

function IdeaNotebook({ state, mutate, busy, contextReady }: { state: TaskState; mutate: Mutate; busy: boolean; contextReady: boolean }) {
  const draft = useEditorDraft<DirectionFields>({ taskId: state.task.task_id, scope: 'idea', baseRefs: {}, initialContent: { core_message: '', hook: '', narrative: '', cta: '' } });
  const [error, setError] = useState('');
  const promote = async () => {
    try {
      const saved = await draft.flush();
      await mutate('/directions/manual', { brief_ref: state.task.current_brief, fields: saved.content });
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not save the idea.'); }
  };
  return <details className="idea-notebook" open={!state.directions.length}><summary>Idea notebook</summary>
    <p className="muted">Saved as you write. Research is optional.</p>
    <div className="grid">{(['core_message', 'hook', 'narrative', 'cta'] as const).map((key) => <Field key={key} label={{ core_message: 'Idea', hook: 'Opening', narrative: 'Story', cta: 'Call to action' }[key]}><textarea disabled={draft.loading || draft.conflict} value={draft.content[key]} onChange={(event) => draft.setContent((previous) => ({ ...previous, [key]: event.target.value }))} /></Field>)}</div>
    <p role="status">{draft.loading ? 'Loading notebook…' : draft.saving ? 'Saving…' : 'Notebook retained in this task'}</p>
    {(draft.error || error) && <p role="alert" className="error">{draft.error || error}</p>}
    <button type="button" className="secondary" disabled={busy || !contextReady || draft.loading || draft.conflict || !Object.values(draft.content).every((value) => value.trim())} onClick={() => void promote()}>Use as a direction</button>
  </details>;
}

function EvidenceList({ direction, state, onSeekEvidence }: { direction: CreativeDirection; state: TaskState; onSeekEvidence?: SeekEvidence }) {
  return <ul className="direction-evidence">{direction.evidence.map((citation, index) => {
    const evidence = directionEvidence(state, citation);
    return <li key={`${citation.analysis_id}:${citation.analysis_revision}:${citation.event_id}:${index}`}>
      <div className="direction-evidence-heading">
        {evidence.canSeek && onSeekEvidence && evidence.frame !== null
          ? <button className="time" type="button" onClick={() => onSeekEvidence(evidence.frame!)} aria-label={`View reference at ${evidence.timeLabel}`}>{evidence.timeLabel} ↗</button>
          : <strong>{evidence.timeLabel}</strong>}
        <small>{evidence.event?.kind.replaceAll('_', ' ') ?? 'Saved evidence'}</small>
      </div>
      <blockquote>{evidence.observation}</blockquote><p>{citation.reason}</p>
      {evidence.mediaDeleted && <p className="muted">Reference media deleted. This saved observation is retained for history.</p>}
      {!evidence.mediaDeleted && !evidence.canSeek && <p className="muted">This historical reference is not available in the current player.</p>}
      <details className="direction-source-record"><summary>Source record</summary><small>Analysis revision {citation.analysis_revision} · {citation.event_id}</small></details>
    </li>;
  })}</ul>;
}

function AuxiliaryNotes({ direction, state, onSeekEvidence }: { direction: CreativeDirection; state: TaskState; onSeekEvidence?: SeekEvidence }) {
  return <>
    {direction.auxiliary_status === 'needs_review' && <p className="notice">Previous-version explanations. These notes were not updated after the creative text changed.</p>}
    <h4>Why it fits the task</h4><p>{direction.rationale}</p>
    <h4>Production requirements</h4><ul>{direction.production_requirements.map((item, index) => <li key={index}>{item}</li>)}</ul>
    <h4>Reference observations and creative interpretation</h4><p className="muted">The observation comes from the reference; the explanation is a creative interpretation.</p>
    <EvidenceList direction={direction} state={state} onSeekEvidence={onSeekEvidence} />
    {direction.hypotheses.length > 0 && <><h4>Hypotheses to test</h4><p className="muted">These are unverified ideas for evaluation, not performance predictions.</p><ul>{direction.hypotheses.map((item, index) => <li key={index}>{item}</li>)}</ul></>}
    {direction.production_notes.length > 0 && <><h4>Production notes</h4>{direction.production_notes.map((item, index) => <p key={index}>{item}</p>)}</>}
    <small>Inputs r{direction.brief_ref.revision} · {direction.analysis_ref ? `Reviewed reference r${direction.analysis_ref.revision}` : 'Original idea · no reference citations'}.</small>
  </>;
}

function readFeedback(key: string): string {
  try { return localStorage.getItem(key) ?? ''; } catch { return ''; }
}

function DirectionCard({ direction, index, selected, onSelect, state, mutate, busy, inputBlocked, onSeekEvidence, onPendingChange }: {
  direction: CreativeDirection; index: number; selected: boolean; onSelect: () => void; state: TaskState; mutate: Mutate; busy: boolean; inputBlocked: boolean;
  onSeekEvidence?: SeekEvidence; onPendingChange: (id: string, pending: boolean) => void;
}) {
  const editor = useEditorDraft<DirectionFields>({
    taskId: state.task.task_id, scope: `direction-${direction.direction_id}`,
    baseRefs: { direction: { id: direction.direction_id, revision: direction.revision } },
    initialContent: { core_message: direction.core_message, hook: direction.hook, narrative: direction.narrative, cta: direction.cta },
  });
  const feedbackKey = `video-anatomy:feedback:${state.task.task_id}:${direction.direction_id}`;
  const [instruction, setInstruction] = useState(() => readFeedback(feedbackKey));
  const [feedbackError, setFeedbackError] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const current = direction.currentness === 'current';
  const auxiliaryStale = direction.auxiliary_status === 'needs_review';
  const dirty = editor.pending;
  const cannotUse = busy || inputBlocked || !state.task.generation_language || !current || dirty || editor.loading || editor.conflict || Boolean(editor.error);
  const inputs = { brief_ref: direction.brief_ref, analysis_ref: direction.analysis_ref, direction_revision: direction.revision };
  useEffect(() => { onPendingChange(direction.direction_id, dirty || editor.conflict || Boolean(editor.error)); }, [direction.direction_id, dirty, editor.conflict, editor.error, onPendingChange]);
  useEffect(() => () => { onPendingChange(direction.direction_id, false); }, [direction.direction_id, onPendingChange]);
  useEffect(() => {
    const sync = (event: Event) => {
      if ((event as CustomEvent<string>).detail === feedbackKey) setInstruction(readFeedback(feedbackKey));
    };
    window.addEventListener('video-anatomy-feedback', sync);
    setInstruction(readFeedback(feedbackKey));
    return () => window.removeEventListener('video-anatomy-feedback', sync);
  }, [feedbackKey]);
  const updateFeedback = (value: string) => {
    setInstruction(value);
    try { localStorage.setItem(feedbackKey, value); setFeedbackError(''); window.dispatchEvent(new CustomEvent('video-anatomy-feedback', { detail: feedbackKey })); }
    catch { setFeedbackError('Feedback could not be saved in this browser. Keep this task open or copy the text before leaving.'); }
  };
  const save = async () => {
    try {
      const saved = await editor.flush();
      const updated = await mutate(`/directions/${direction.direction_id}/edit`, { direction_revision: direction.revision, fields: saved.content, expected_editor_version: saved.draft_version });
      if (updated) await editor.reload();
    } catch { /* The draft channel keeps the text and displays its error. */ }
  };
  return <article className={`direction${selected ? ' selected' : ''}`} aria-label={`Direction ${String.fromCharCode(65 + index)}`}>
    <div className="direction-card-heading"><div><p className="m2-eyebrow">DIRECTION {String.fromCharCode(65 + index)}</p><h3>{direction.analysis_ref ? index === 0 ? 'Follow the reference' : 'Reframe the story' : 'Original approach'}</h3></div><span className="direction-letter" aria-hidden="true">{String.fromCharCode(65 + index)}</span></div>
    <p className="direction-badges"><Badge warning={!current}>{current ? 'Current version' : 'Historical version'}</Badge><Badge warning={direction.approval_status === 'draft'}>{direction.approval_status === 'approved' ? 'Approved' : 'Not approved'}</Badge><small>revision {direction.revision}</small></p>
    <dl className="direction-comparison">
      <div><dt>The idea</dt><dd>{direction.core_message}</dd></div><div><dt>Opening / Hook</dt><dd>{direction.hook}</dd></div><div><dt>Story structure</dt><dd>{direction.narrative}</dd></div>
      {!auxiliaryStale && <><div><dt>Brand fit</dt><dd>{direction.rationale}</dd></div><div><dt>What to prepare</dt><dd><ul>{direction.production_requirements.map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</ul></dd></div></>}
    </dl>
    {auxiliaryStale && <p className="notice">The text was manually edited. Supporting explanations belong to the previous version and have not been updated.</p>}
    <details className="direction-full"><summary>Read full direction and edit</summary>
      <p className="muted">Edit the four creative fields below. A saved change creates a new version that needs approval again.</p>
      <form onSubmit={(event) => { event.preventDefault(); void save(); }}><fieldset disabled={busy || editor.loading}>
        {(['core_message', 'hook', 'narrative', 'cta'] as const).map((key) => <Field key={key} label={{ core_message: 'Core message', hook: 'Hook', narrative: 'Narrative', cta: 'CTA' }[key]}><textarea required readOnly={!current || editor.conflict} value={editor.content[key]} onChange={(event) => editor.setContent((previous) => ({ ...previous, [key]: event.target.value }))} /></Field>)}
        <div className="actions"><button type="submit" className="secondary" disabled={!current || editor.conflict || !dirty || editor.saving}>Save direction edits</button><button type="button" className="text-button" disabled={!dirty || editor.saving} onClick={() => setDiscarding(true)}>Discard draft changes</button></div>
      </fieldset></form>
      <p className="direction-draft-status" role="status">{editor.loading ? 'Loading your saved draft…' : editor.saving ? 'Saving recoverable draft…' : dirty ? 'Draft changes retained · not yet applied to this direction' : 'No pending text changes'}</p>
      {editor.error && <div className="error" role="alert">{editor.error}<button type="button" className="text-button" onClick={() => { void (editor.loading ? editor.reload() : editor.flush()).catch(() => undefined); }}>{editor.loading ? 'Retry loading draft' : 'Retry draft save'}</button></div>}
      {editor.conflict && <div className="notice"><p>The saved direction changed while this draft was open. Your draft is retained. Copy any text you need, then discard this draft to load the current direction.</p><button type="button" className="secondary" onClick={() => setDiscarding(true)}>Review discard options</button></div>}
      {!current && dirty && <p className="notice">This direction became historical after its inputs changed. Your draft is retained for copying. Discard the pending draft when ready to generate new directions.</p>}
      {discarding && <div className="notice" role="alert"><p>Discard these draft edits and restore the saved direction? Saved versions remain available in history.</p><div className="actions"><button type="button" disabled={editor.saving} onClick={async () => { try { await editor.discard(); setDiscarding(false); } catch { /* Error stays in the draft channel. */ } }}>Discard draft</button><button type="button" className="secondary" onClick={() => setDiscarding(false)}>Keep editing</button></div></div>}
      <details className="direction-auxiliary"><summary>{auxiliaryStale ? 'Previous-version explanations · not updated after your edits' : 'Evidence, explanation and production notes'}</summary><AuxiliaryNotes direction={direction} state={state} onSeekEvidence={onSeekEvidence} /></details>
      <form onSubmit={async (event) => { event.preventDefault(); if (await mutate(`/directions/${direction.direction_id}/refine`, { ...inputs, instruction })) updateFeedback(''); }}><fieldset disabled={cannotUse}>
        <Field label="Refinement instruction" hint={state.task.mode === 'sample' ? 'Offline sample understands “make it presenter-free”. Other instructions are retained as notes and explicitly marked not interpreted.' : 'Describe the change you want. AI creates a new draft and updates its explanation; you review and approve it separately.'}><textarea value={instruction} onChange={(event) => updateFeedback(event.target.value)} placeholder="Make it presenter-free" required /></Field><button type="submit" disabled={!instruction.trim()}>Apply instruction</button>
      </fieldset>{feedbackError ? <p className="error" role="alert">{feedbackError}</p> : instruction && <p className="muted">Unsent feedback is kept in this browser when you switch tasks.</p>}</form>
    </details>
    <div className="direction-decision"><label className="select-choice"><input type="radio" name="direction" checked={selected} onChange={onSelect} disabled={busy || !current} />Select this direction</label><p className="muted">Selection is a preference. Approval authorizes this exact saved version for production.</p>
      {auxiliaryStale && current && direction.approval_status !== 'approved' && <label className="direction-acknowledgement"><input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />I reviewed the edited text and understand that its previous explanations are not updated.</label>}
      <button type="button" disabled={cannotUse || !selected || (auxiliaryStale && !acknowledged) || direction.approval_status === 'approved'} onClick={() => { void mutate(`/directions/${direction.direction_id}/approve`, inputs); }}>Approve this direction</button>
      {dirty && <p className="muted">Save or discard pending text before refinement, approval or production. Any previous approval remains attached to its saved version.</p>}
    </div>
  </article>;
}

function LanguageChoice({ state, mutate, busy, pending, onPendingChange }: { state: TaskState; mutate: Mutate; busy: boolean; pending: boolean; onPendingChange: (pending: boolean) => void }) {
  const currentLanguage = state.task.generation_language;
  const [language, setLanguage] = useState<GenerationLanguage | ''>(currentLanguage ?? '');
  const changing = Boolean(currentLanguage && language && language !== currentLanguage);
  const hasCreative = state.directions.length > 0 || state.production_briefs.length > 0;
  const unsaved = language !== (currentLanguage ?? '');
  useEffect(() => { onPendingChange(unsaved); return () => onPendingChange(false); }, [unsaved, onPendingChange]);
  return <form className="direction-language" onSubmit={(event) => { event.preventDefault(); if (language) void mutate('/language', { generation_language: language }); }}>
    <div><Field label="Generation language" hint="Used for directions, the production brief and newly written dialogue. Source evidence and confirmed fixed wording keep their original language."><select value={language} onChange={(event) => setLanguage(event.target.value as GenerationLanguage | '')} disabled={busy}><option value="">Choose a language</option><option value="English">English</option><option value="Chinese">中文 · Chinese</option></select></Field></div>
    <button type="submit" className="secondary" disabled={busy || pending || !language || language === currentLanguage}>Save generation language</button>
    {unsaved && <button type="button" className="text-button" disabled={busy} onClick={() => setLanguage(currentLanguage ?? '')}>Reset language choice</button>}
    {changing && hasCreative && <p className="notice">Saving a different language makes existing directions and production materials historical. Generate and approve a new direction to continue. Your reference analysis and review are retained.</p>}
  </form>;
}

export default function Directions({ state, mutate, busy, m2Blocked, analysisBlocked = false, onSeekEvidence }: {
  state: TaskState; mutate: Mutate; busy: boolean; m2Blocked: boolean; analysisBlocked?: boolean; onSeekEvidence?: SeekEvidence;
}) {
  const [referenceChoice, setUseReference] = useState<boolean | null>(null);
  const [handoff, setHandoff] = useState<{ title: string; analysis_ref: { id: string; revision: number }; methods: { id: string; title: string; conditions: string[] }[] } | null>(null);
  useEffect(() => {
    let alive = true;
    const reload = () => { void request<typeof handoff>(`/tasks/${state.task.task_id}/structure/handoff`).then((value) => { if (alive) setHandoff(value); }).catch(() => { if (alive) setHandoff(null); }); };
    reload(); window.addEventListener('structure-handoff', reload);
    return () => { alive = false; window.removeEventListener('structure-handoff', reload); };
  }, [state.task.task_id]);
  const [pendingByDirection, setPendingByDirection] = useState<Record<string, boolean>>({});
  const [languagePending, setLanguagePending] = useState(false);
  const [onPendingChange] = useState(() => (id: string, pending: boolean) => setPendingByDirection((previous) => previous[id] === pending ? previous : { ...previous, [id]: pending }));
  const latest = Array.from(new Map(state.directions.map((direction) => [direction.direction_id, direction])).values());
  const current = latest.filter((direction) => direction.currentness === 'current');
  const choices = current.length ? current : latest.slice(-2);
  const displayed = new Set(choices.map((direction) => `${direction.direction_id}:${direction.revision}`));
  const history = state.directions.filter((direction) => !displayed.has(`${direction.direction_id}:${direction.revision}`));
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  const video = state.videos.find((item) => item.video_id === analysis?.video_id);
  const referenceReady = Boolean(analysis?.review.user_confirmed && analysis.status === 'succeeded' && analysis.frame_count !== null && video?.frame_timing && !video.deleted_at);
  // Once a source was reviewed, retain that reference intent across corrections;
  // never silently switch a pending reference workflow to original generation.
  const useReference = referenceChoice ?? (referenceReady || state.analyses.some((item) => item.review.user_confirmed));
  const ready = Boolean(state.task.current_brief && (!useReference || referenceReady));
  const directionPending = Object.values(pendingByDirection).some(Boolean);
  const inputBlocked = m2Blocked || (useReference && analysisBlocked);
  return <section id="directions" className="directions-workspace" aria-labelledby="directions-heading">
    <div className="direction-heading"><div><h2 id="directions-heading">Ideas</h2><p className="muted">Start with a thought, or ask for two approaches to your brief.</p></div></div>
    <IdeaNotebook key={state.task.task_id} state={state} mutate={mutate} busy={busy} contextReady={Boolean(state.task.current_brief) && !m2Blocked} />
    {handoff && <aside className="notice"><strong>From Structure: {handoff.title}</strong>{handoff.analysis_ref.id !== state.task.current_analysis?.id || handoff.analysis_ref.revision !== state.task.current_analysis?.revision ? <p>Its source has changed. This saved selection will not be used for generation.</p> : <><p>Selected research informs inspiration; it does not confirm new product claims.</p><ul>{handoff.methods.map((method) => <li key={method.id}>{method.title}{method.conditions.length > 0 && <small> · {method.conditions.join('; ')}</small>}</li>)}</ul></>}</aside>}
    {state.task.mode === 'sample' && <p className="notice">Fictional offline sample. It demonstrates the workflow, not recognition accuracy or creative effectiveness.</p>}
    <LanguageChoice key={`${state.task.task_id}:${state.task.generation_language}`} state={state} mutate={mutate} busy={busy} pending={directionPending} onPendingChange={setLanguagePending} />
    <label><input type="checkbox" checked={useReference} onChange={(event) => setUseReference(event.target.checked)} disabled={busy} /> Use reviewed reference evidence</label>
    <div className="direction-generation"><button type="button" disabled={busy || inputBlocked || directionPending || languagePending || !ready || !state.task.generation_language} onClick={() => { void mutate('/directions/generate', { brief_ref: state.task.current_brief, analysis_ref: useReference ? state.task.current_analysis : null, use_reference: useReference }); }}>{busy ? 'Working…' : `Generate two ${state.directions.length ? 'new ' : ''}${state.task.mode === 'sample' ? 'sample ' : ''}directions`}</button><p className="muted">{useReference ? 'Compare two ways to adapt reviewed evidence.' : 'Explore original approaches from your applied brief.'}</p></div>
    {!state.task.current_brief && <p className="notice">Apply your context to generate directions. You can keep writing in your notebook.</p>}
    {useReference && !referenceReady && <p className="notice">Review the reference in Timeline, or turn off reference evidence to generate an original idea.</p>}
    {!state.task.generation_language && <p className="muted">Choose and save a language before generation or approval.</p>}
    {inputBlocked && <p className="notice">Resolve pending brand inputs or reference corrections before new creative actions. Existing work remains available.</p>}
    {directionPending && <p className="notice">A direction has a pending draft. Save or discard it before generating alternatives or changing the generation language.</p>}
    {languagePending && <p className="notice">Save or reset the language choice before generating, refining or approving a direction.</p>}
    {choices.length > 0 && <div className="direction-grid">{choices.map((direction, index) => <DirectionCard key={`${state.task.task_id}:${direction.direction_id}:${direction.revision}`} direction={direction} index={index} selected={state.task.chosen_direction?.id === direction.direction_id && state.task.chosen_direction.revision === direction.revision} onSelect={() => { void mutate(`/directions/${direction.direction_id}/select`, { direction_revision: direction.revision }); }} state={state} mutate={mutate} busy={busy} inputBlocked={m2Blocked || (Boolean(direction.analysis_ref) && analysisBlocked) || languagePending} onSeekEvidence={onSeekEvidence} onPendingChange={onPendingChange} />)}</div>}
    {state.feedback.length > 0 && <details className="direction-history"><summary>Saved refinement instructions ({state.feedback.length})</summary>{state.feedback.map((feedback) => <div key={feedback.feedback_id}><p><strong>{feedback.instruction}</strong> <Badge warning={feedback.status !== 'applied'}>{feedback.status.replaceAll('_', ' ')}</Badge></p><p>{feedback.explanation}</p><small>Target revision {feedback.target_direction.revision}{feedback.resulting_direction ? ` → draft revision ${feedback.resulting_direction.revision}; approval required.` : ''}</small></div>)}</details>}
    {history.length > 0 && <details className="direction-history"><summary>Previous direction versions ({history.length})</summary>{[...history].reverse().map((direction) => <details key={`${direction.direction_id}:${direction.revision}`}><summary>{direction.core_message} · revision {direction.revision}</summary><p className="muted">{direction.currentness} · {direction.approval_status} · {direction.origin.description}</p><dl className="direction-comparison"><div><dt>Hook</dt><dd>{direction.hook}</dd></div><div><dt>Narrative</dt><dd>{direction.narrative}</dd></div><div><dt>CTA</dt><dd>{direction.cta}</dd></div></dl><AuxiliaryNotes direction={direction} state={state} onSeekEvidence={onSeekEvidence} /></details>)}</details>}
  </section>;
}
