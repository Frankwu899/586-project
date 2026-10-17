import { useEffect, useState } from 'react';
import type { AnalysisResult, ContentSegment, EvidenceEvent, FrameTiming } from './generated/contracts';
import { Badge, Field, seconds, type Mutate } from './ui';
import { frameRangeLabel } from './timing';
import { useEditorDraft } from './useEditorDraft';
import { analysisCorrections, evidenceLanes, type AnalysisEditorContent } from './analysisReviewModel';
import VisualDetailsEditor from './VisualDetailsEditor';
import './m5.css';

type Role = ContentSegment['roles'][number];
const roleLabels: Record<Role, string> = { hook: 'Hook', product_demo: 'Product presentation/demo', proof: 'Demonstration/result', cta: 'CTA', other: 'Other / uncertain' };
const kindLabels: Record<EvidenceEvent['kind'], string> = { visual_action: 'Visual observation', on_screen_text: 'Visible text', speech: 'Speech', music: 'Music', sfx: 'Sound effect' };
const coverageLabels = { observations: 'Observations available', none_found: 'Checked; none found', not_analyzed: 'Not analyzed', failed: 'Extraction failed' };

function VisualSummary({ event }: { event: EvidenceEvent }) {
  const details = event.visual_details;
  if (!details) return <p className="muted">Structured visual details were not analyzed for this observation.</p>;
  return <dl className="m5-visual-summary">
    {(Object.keys(details) as Array<keyof typeof details>).map((kind) => { const group = details[kind]; return <div key={kind}>
      <dt>{kind === 'product_presentations' ? 'Product presentation' : kind === 'subjects' ? 'Subjects' : 'Actions'}</dt>
      <dd>{group.status === 'observations' ? <ul>{group.items.map((item, index) => <li key={index}>{'label' in item ? item.label : item.description}</li>)}</ul> : coverageLabels[group.status]}
        {group.error && <p className="error">{group.error.message}</p>}
      </dd>
    </div>; })}
  </dl>;
}

export default function AnalysisReview({ taskId, analysis, frameTiming, mutate, busy, seek, canSeek, onPendingChange }: {
  taskId: string; analysis: AnalysisResult; frameTiming?: FrameTiming | null; mutate: Mutate; busy: boolean;
  seek: (frame: number) => void; canSeek: boolean; onPendingChange?: (pending: boolean) => void;
}) {
  const analysisRef = { id: analysis.analysis_id, revision: analysis.revision };
  const draft = useEditorDraft<AnalysisEditorContent>({ taskId, scope: 'analysis', baseRefs: { analysis: analysisRef }, initialContent: { events: analysis.events, segments: analysis.segments } });
  const { events, segments } = draft.content;
  const [editing, setEditing] = useState<string[]>([]);
  const [actionError, setActionError] = useState('');
  const [acting, setActing] = useState(false);
  const [discardRequested, setDiscardRequested] = useState(false);
  const corrections = analysisCorrections(analysis, draft.content);
  const dirty = corrections.event_edits.length + corrections.segment_edits.length > 0;
  const pending = dirty || draft.pending || draft.conflict;
  const editable = analysis.status === 'succeeded' || analysis.status === 'partial';
  const locked = busy || acting || draft.loading;
  const hasFrameTiming = Boolean(frameTiming && analysis.frame_count !== null);
  const lanes = evidenceLanes(events);

  useEffect(() => { onPendingChange?.(pending); }, [onPendingChange, pending]);

  const updateEvent = (id: string, patch: Partial<Pick<EvidenceEvent, 'text' | 'description' | 'visual_details'>>) => draft.setContent({
    ...draft.content, events: events.map((event) => event.event_id === id ? { ...event, ...patch } : event),
  });
  const toggleRole = (id: string, role: Role) => draft.setContent({ ...draft.content, segments: segments.map((segment) => {
    if (segment.segment_id !== id) return segment;
    const next = role === 'other' ? ['other'] : segment.roles.includes(role) ? segment.roles.filter((item) => item !== role) : [...segment.roles.filter((item) => item !== 'other'), role];
    return { ...segment, roles: (next.length ? next : ['other']) as ContentSegment['roles'] };
  }) });
  const run = async (action: () => Promise<unknown>) => {
    setActing(true); setActionError('');
    try { await action(); } catch (error) { setActionError(error instanceof Error ? error.message : 'The operation could not finish. Your corrections are still here.'); }
    finally { setActing(false); }
  };
  const apply = () => run(async () => {
    const saved = await draft.flush();
    if (saved.conflict) throw new Error('The saved analysis changed. Resolve the draft conflict before applying corrections.');
    await mutate('/analysis/correct', { analysis_ref: analysisRef, expected_editor_version: saved.draft_version, ...corrections });
  });
  const exactRange = (item: EvidenceEvent | ContentSegment) => {
    if (frameTiming && item.start_frame !== null && item.end_frame !== null) return frameRangeLabel(item.start_frame, item.end_frame, frameTiming);
    return item.legacy_seconds ? `${seconds(item.legacy_seconds.start_seconds)}–${seconds(item.legacy_seconds.end_seconds)} · saved legacy timing` : 'Frame timing unavailable';
  };
  const clock = (value: number) => {
    const centiseconds = Math.round(value * 100);
    return `${Math.floor(centiseconds / 6000).toString().padStart(2, '0')}:${((centiseconds % 6000) / 100).toFixed(2).padStart(5, '0')}`;
  };
  const timeLabel = (event: EvidenceEvent) => {
    if (frameTiming && event.start_frame !== null && event.end_frame !== null) {
      const start = clock(frameTiming.frame_boundaries_seconds[event.start_frame]);
      return event.kind === 'visual_action' || event.kind === 'on_screen_text' ? start : `${start}–${clock(frameTiming.frame_boundaries_seconds[event.end_frame])}`;
    }
    return event.legacy_seconds ? `${clock(event.legacy_seconds.start_seconds)} · legacy` : 'No verified timing';
  };
  const eventView = (event: EvidenceEvent, index: number) => {
    const isEditing = editing.includes(event.event_id);
    const label = `${kindLabels[event.kind].toLowerCase()} ${index + 1}`;
    const editableText = event.kind === 'speech' || event.kind === 'on_screen_text';
    const associatedRoles = [...new Set(segments.filter((segment) => segment.evidence_ids.includes(event.event_id)).flatMap((segment) => segment.roles))];
    return <article className={`m5-observation m5-${event.kind}`} key={event.event_id} data-evidence-id={event.event_id} aria-label={label}>
      <div className="m5-event-topline">
        <span className="m5-kind">{kindLabels[event.kind]}</span>
        <button className="time" type="button" aria-label={`Play ${label} at ${timeLabel(event)}`} title={exactRange(event)} disabled={!canSeek || event.start_frame === null} onClick={() => event.start_frame !== null && seek(event.start_frame)}>{timeLabel(event)} <span aria-hidden="true">↗</span></button>
      </div>
      <p className={`m5-observation-copy${editableText ? ' m5-quotation' : ''}`}>{editableText ? event.text : event.description}</p>
      {event.kind === 'visual_action' && associatedRoles.length > 0 && <p className="m5-role-labels"><span>Possible content role</span> {associatedRoles.map((role) => <span key={role}>{roleLabels[role]}</span>)}</p>}
      {event.uncertainty && <p className="m5-uncertainty">Uncertainty: {event.uncertainty}</p>}
      {editable && (editableText || event.kind === 'visual_action') && <button type="button" className="text-button" aria-expanded={isEditing} aria-controls={`correct-${event.event_id}`} disabled={locked} onClick={() => setEditing((items) => isEditing ? items.filter((id) => id !== event.event_id) : [...items, event.event_id])}>{isEditing ? 'Close correction' : `Correct ${label}`}</button>}
      {isEditing && <fieldset className="m5-correction" id={`correct-${event.event_id}`} disabled={locked}>
        <legend>Correct this observation</legend>
        {editableText && <Field label={event.kind === 'speech' ? 'Recognized speech' : 'Recognized visible text'} hint="Keep the original language. Correct recognition errors without adding a new claim."><textarea aria-label={`Recognized text · ${event.event_id}`} value={event.text ?? ''} onChange={(change) => updateEvent(event.event_id, { text: change.target.value })} /></Field>}
        {event.kind === 'visual_action' && <><Field label="What is visible"><textarea aria-label={`Visual description · ${event.event_id}`} value={event.description ?? ''} onChange={(change) => updateEvent(event.event_id, { description: change.target.value })} /></Field><details><summary>Correct subjects, actions or product labels</summary><VisualDetailsEditor eventId={event.event_id} value={event.visual_details} onChange={(visual_details) => updateEvent(event.event_id, { visual_details })} /></details></>}
        <p className="muted">Automatically kept as a draft. Apply all corrections below to update the saved analysis.</p>
      </fieldset>}
      <details className="m5-source-details"><summary>{event.kind === 'visual_action' ? 'Observed details & source' : 'Source & timing'}</summary>
        {event.kind === 'visual_action' && <VisualSummary event={event} />}
        {editableText && event.description && <p>{event.description}</p>}
        <p className="muted">{event.source} · {event.method}</p><p className="muted">{exactRange(event)}</p>
        <p className="muted">The recorded interval locates this evidence; sampled visuals do not establish a continuous shot or action duration.</p>
      </details>
    </article>;
  };

  return <section className="panel m5" aria-labelledby="analysis-heading">
    <div className="m5-heading"><div><p className="m5-eyebrow">REFERENCE / EVIDENCE NOTEBOOK</p><h2 id="analysis-heading">Read the reference.</h2><p>Check what was observed, correct what needs care, then confirm it for creative work.</p></div><div className="m5-review-status"><Badge warning={analysis.origin.kind === 'sample'}>{analysis.origin.kind === 'sample' ? 'Fictional sample evidence' : `${analysis.origin.kind} evidence`}</Badge><Badge warning={analysis.status !== 'succeeded'}>{analysis.status}</Badge><span>Revision {analysis.revision}</span><strong>{analysis.review.user_confirmed ? 'Review confirmed' : 'Awaiting your review'}</strong></div></div>
    <div className="m5-coverage-note"><strong>A sampled view, with its limits.</strong><p>Visuals and visible text cover sampled frames, not every shot. Speech is listed separately in time order, including speech without a matching visual sample. “Not analyzed” never means absent.</p></div>
    <div className="m5-coverage" aria-label="Analysis coverage">{(Object.keys(analysis.coverage) as EvidenceEvent['kind'][]).map((kind) => { const status = analysis.coverage[kind]; return <div key={kind}><span>{kindLabels[kind]}</span><strong className={status === 'failed' ? 'm5-failed' : ''}>{coverageLabels[status]}</strong></div>; })}</div>
    <details className="m5-provenance"><summary>About this analysis & its preserved history</summary><p>{analysis.origin.description}</p><p className="muted">Original extraction and every applied correction remain in history. Reference timing, source identity and extraction status are read-only. Role labels are interpretations, not proof of effectiveness.</p><p className="muted">{analysis.corrections.length} recorded corrections · Original revision {analysis.original_revision}. Frame ranges include the start and exclude the end; storyboard timing uses a separate clock.</p></details>
    {!hasFrameTiming && <p className="notice">This legacy analysis has no verified frame timing. Its saved seconds remain visible. Reanalyze an available source video before confirming it.</p>}
    {analysis.error && <p role="alert" className="error">{analysis.error.message}</p>}
    {analysis.empty_result_reason && <p className="notice">{analysis.empty_result_reason}</p>}
    {analysis.status === 'partial' && <p className="notice">Partial analysis: successful observations remain readable and correctable. Rerun analysis to resolve failed extraction groups before confirming this reference for creative work.</p>}
    <div className="m5-draft-state" role="status" aria-live="polite"><span className={`m5-status-dot${pending ? ' pending' : ''}`} aria-hidden="true" /><strong>{draft.loading ? 'Restoring corrections…' : draft.saving ? 'Saving correction draft…' : draft.error ? 'Correction draft needs attention' : pending ? 'Correction draft kept · not yet applied' : analysis.review.user_confirmed ? 'Saved analysis confirmed for creative work' : 'Saved analysis ready to review'}</strong>{pending && <span>Apply and confirm, or discard, before new creative work or reanalysis.</span>}</div>
    {(actionError || draft.error) && <div role="alert" className="error"><p>{actionError || draft.error}</p><button type="button" className="secondary" disabled={busy || acting || draft.saving} onClick={() => void run(() => draft.loading ? draft.reload() : draft.flush())}>{draft.loading ? 'Retry loading corrections' : 'Retry draft save'}</button></div>}
    {draft.conflict && <div className="notice"><strong>The saved analysis changed while this draft was open.</strong><p>Your draft has been preserved below. Copy any corrections you want to keep before explicitly discarding this draft to load the saved version. Nothing is applied automatically.</p></div>}
    <div className="m5-evidence-columns">
      <section aria-labelledby="m5-visual-heading"><div className="m5-lane-heading"><h3 id="m5-visual-heading">Visual observations</h3><span>{lanes.visuals.length} recorded</span></div><p className="muted">Selected evidence points. Gaps between observations are not analyzed shots.</p>{lanes.visuals.length ? lanes.visuals.map(eventView) : <p className="m5-empty">{coverageLabels[analysis.coverage.visual_action]}. No visual observations to display.</p>}</section>
      <section aria-labelledby="m5-words-heading"><div className="m5-lane-heading"><h3 id="m5-words-heading">Speech & visible text</h3><span>{lanes.words.length} recorded</span></div><p className="muted">Original-language words, in time order. Speech and on-screen text stay distinct.</p>{lanes.words.length ? lanes.words.map(eventView) : <p className="m5-empty">No recognized words to display. Check coverage above for what was analyzed.</p>}</section>
    </div>
    {lanes.sounds.length > 0 && <section className="m5-sounds"><h3>Other audio observations</h3>{lanes.sounds.map(eventView)}</section>}
    {segments.length > 0 && <details className="m5-role-sections"><summary>Content role interpretations · {segments.length} sections</summary><p className="muted">These labels interpret groups of observations. They are not continuous shot boundaries or verified performance claims.</p>{segments.map((segment, index) => <details key={segment.segment_id}><summary>Section {index + 1} · {segment.roles.map((role) => roleLabels[role]).join(', ')}</summary><p className="muted">{exactRange(segment)} · {segment.evidence_ids.length} linked observations</p>{segment.interpretation && <p>{segment.interpretation}</p>}<fieldset disabled={locked || !editable}><legend>Section {index + 1} roles</legend><div className="roles">{(Object.keys(roleLabels) as Role[]).map((role) => <label key={role}><input type="checkbox" checked={segment.roles.includes(role)} onChange={() => toggleRole(segment.segment_id, role)} />{roleLabels[role]}</label>)}</div></fieldset></details>)}</details>}
    {editable && <div className="m5-review-actions"><div><h3>{pending ? 'Bring your corrections into the analysis.' : analysis.review.user_confirmed ? 'Ready for creative work.' : 'Ready to use this evidence?'}</h3><p>{pending ? 'Applying creates a new analysis revision. Review confirmation is a separate step.' : 'Confirmation lets creative planning use this revision. It does not certify every observation as accurate.'}</p></div><div className="actions"><button type="button" disabled={locked || !dirty || draft.conflict} onClick={() => void apply()}>Save analysis corrections</button><button type="button" className="secondary" disabled={locked || pending || analysis.review.user_confirmed || !hasFrameTiming || analysis.status !== 'succeeded'} onClick={() => void run(async () => { await draft.flush(); await mutate('/analysis/confirm', { analysis_ref: analysisRef }); })}>Use this reviewed analysis</button>{pending && <button type="button" className="text-button" disabled={locked} onClick={() => setDiscardRequested(true)}>Discard corrections</button>}</div>{discardRequested && <div className="notice" role="group" aria-label="Confirm discard corrections"><p>Discard these draft corrections and return to the saved analysis? Previously applied revisions remain in history.</p><div className="actions"><button type="button" disabled={locked} onClick={() => void run(async () => { await draft.discard(); setDiscardRequested(false); setEditing([]); })}>Discard draft changes</button><button type="button" className="secondary" onClick={() => setDiscardRequested(false)}>Keep editing</button></div></div>}</div>}
  </section>;
}
