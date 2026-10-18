import { useEffect, useState } from 'react';
import { createPortal } from 'react-dom';
import type { AnalysisResult, ContentSegment, EvidenceEvent, FrameTiming } from './generated/contracts';
import { Badge, Field, seconds, type Mutate } from './ui';
import { frameRangeLabel } from './timing';
import { useEditorDraft } from './useEditorDraft';
import { analysisCorrections, repeatedTextGroups, type AnalysisEditorContent } from './analysisReviewModel';
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

export default function AnalysisReview({ taskId, analysis, frameTiming, mutate, busy, seek, canSeek, onPendingChange, inspectorTarget, timelineTarget, currentFrame = 0 }: {
  taskId: string; analysis: AnalysisResult; frameTiming?: FrameTiming | null; mutate: Mutate; busy: boolean;
  seek: (frame: number) => void; canSeek: boolean; onPendingChange?: (pending: boolean) => void;
  inspectorTarget?: HTMLElement | null; timelineTarget?: HTMLElement | null; currentFrame?: number;
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
  const [selectedId, setSelectedId] = useState(events[0]?.event_id ?? '');
  const selected = events.find((event) => event.event_id === selectedId) ?? events[0];
  const duration = frameTiming?.frame_boundaries_seconds[frameTiming.frame_count] ?? analysis.duration_seconds ?? 1;
  const positioned = (item: EvidenceEvent | ContentSegment) => {
    const start = frameTiming && item.start_frame !== null ? frameTiming.frame_boundaries_seconds[item.start_frame] : item.legacy_seconds?.start_seconds ?? 0;
    const end = frameTiming && item.end_frame !== null ? frameTiming.frame_boundaries_seconds[item.end_frame] : item.legacy_seconds?.end_seconds ?? start;
    return { left: `${Math.min(99.5, start / duration * 100)}%`, width: `${Math.max(.3, (end - start) / duration * 100)}%` };
  };
  const select = (event: EvidenceEvent) => { setSelectedId(event.event_id); if (canSeek && event.start_frame !== null) seek(event.start_frame); };
  const groupedWords = repeatedTextGroups(events);
  const wordsAtSample = selected?.kind === 'on_screen_text' ? events.filter((event) => event.kind === 'on_screen_text' && event.start_frame === selected.start_frame && event.legacy_seconds?.start_seconds === selected.legacy_seconds?.start_seconds) : [];
  const uniqueTextPoints = events.filter((event, index) => event.kind === 'on_screen_text' && !events.slice(0, index).some((prior) => prior.kind === 'on_screen_text' && prior.start_frame === event.start_frame && prior.legacy_seconds?.start_seconds === event.legacy_seconds?.start_seconds));
  const selectedWordGroup = selected?.kind === 'on_screen_text' ? groupedWords.get((selected.text ?? '').normalize('NFKC').replace(/\s+/g, ' ').trim()) : undefined;

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
    if (!await mutate('/analysis/correct', { analysis_ref: analysisRef, expected_editor_version: saved.draft_version, ...corrections })) throw new Error('Corrections were not applied. Your draft is retained; resolve the error and retry.');
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

  const inspector = <section className="m5 m5-inspector" aria-label="Selected annotation">
    <div className="m5-inspector-heading"><strong>Selected annotation</strong><Badge warning={!analysis.review.user_confirmed}>{analysis.review.user_confirmed ? 'Reviewed' : 'Review'}</Badge></div>
    {(analysis.error || actionError || draft.error) && <p role="alert" className="error">{analysis.error?.message || actionError || draft.error}</p>}
    {analysis.status === 'partial' && <p className="notice">Partial results. Completed observations are available; failed extraction needs a new analysis.</p>}
    {wordsAtSample.length > 1 && <label className="m5-text-selector">Text at this sample<select aria-label="Visible text at selected sample" value={selected.event_id} onChange={(event) => setSelectedId(event.target.value)}>{wordsAtSample.map((item) => <option key={item.event_id} value={item.event_id}>{item.text}</option>)}</select></label>}
    {draft.error && <button type="button" className="secondary" disabled={busy || acting || draft.saving} onClick={() => void run(() => draft.loading ? draft.reload() : draft.flush())}>{draft.loading ? 'Retry loading corrections' : 'Retry draft save'}</button>}
    {selected ? eventView(selected, events.findIndex((event) => event.event_id === selected.event_id)) : <p className="m5-empty">{analysis.empty_result_reason ?? 'No observations available. Check extraction coverage.'}</p>}
    {selectedWordGroup && selectedWordGroup.length > 1 && <details className="m5-repeat-group"><summary>Same text at {selectedWordGroup.length} sampled points</summary><p className="muted">Grouped for review, not removed. Visibility between these points is unknown.</p><div className="actions">{selectedWordGroup.map((event) => <button key={event.event_id} type="button" className="secondary" onClick={() => select(event)} aria-pressed={event.event_id === selected.event_id}>{timeLabel(event)}</button>)}</div></details>}
    {selected && segments.filter((segment) => segment.evidence_ids.includes(selected.event_id)).map((segment) => <details className="m5-role-sections" key={segment.segment_id}><summary>Possible role · {segment.roles.map((role) => roleLabels[role]).join(', ')}</summary><p>{segment.interpretation}</p><fieldset disabled={locked || !editable}><legend>Content role interpretation</legend><div className="roles">{(Object.keys(roleLabels) as Role[]).map((role) => <label key={role}><input type="checkbox" checked={segment.roles.includes(role)} onChange={() => toggleRole(segment.segment_id, role)} />{roleLabels[role]}</label>)}</div></fieldset></details>)}
    <details className="m5-provenance"><summary>Coverage and source</summary><p>{analysis.origin.description}</p><div className="m5-coverage">{(Object.keys(analysis.coverage) as EvidenceEvent['kind'][]).map((kind) => <div key={kind}><span>{kindLabels[kind]}</span><strong>{coverageLabels[analysis.coverage[kind]]}</strong></div>)}</div><p>{analysis.corrections.length} recorded corrections · Revision {analysis.revision}. Original observations remain in history.</p></details>
    <div className="m5-draft-state" role="status" aria-live="polite">{draft.loading ? 'Restoring corrections…' : draft.saving ? 'Saving draft…' : pending ? 'Correction draft saved separately' : analysis.review.user_confirmed ? 'Reviewed revision saved' : 'No unsaved corrections'}</div>
    {draft.conflict && <p className="notice">The saved analysis changed. Your draft is retained; discard it explicitly to load the saved version.</p>}
    {editable && <div className="m5-review-actions">
      {dirty && <button type="button" disabled={locked || draft.conflict} onClick={() => void apply()}>{acting ? 'Saving…' : 'Save analysis corrections'}</button>}
      <button type="button" disabled={locked || pending || analysis.review.user_confirmed || !hasFrameTiming || analysis.status !== 'succeeded'} onClick={() => void run(async () => { await draft.flush(); if (!await mutate('/analysis/confirm', { analysis_ref: analysisRef })) throw new Error('Review could not be saved. Your analysis is retained.'); })}>{analysis.review.user_confirmed ? 'Analysis reviewed' : 'Use this reviewed analysis'}</button>
      {pending && <button type="button" className="text-button" disabled={locked} onClick={() => setDiscardRequested(true)}>Discard corrections</button>}
      {discardRequested && <div className="notice" role="group" aria-label="Confirm discard corrections"><p>Discard this draft? Applied revisions remain in history.</p><button type="button" disabled={locked} onClick={() => void run(async () => { await draft.discard(); setDiscardRequested(false); setEditing([]); })}>Discard draft changes</button><button type="button" className="secondary" onClick={() => setDiscardRequested(false)}>Keep editing</button></div>}
    </div>}
  </section>;
  const mark = (event: EvidenceEvent, point: boolean) => <button key={event.event_id} type="button"
    className={`timeline-mark ${point ? 'sample-point' : 'timed-span'} ${event.kind}${selected?.event_id === event.event_id ? ' selected' : ''}`}
    style={point ? { left: positioned(event).left } : positioned(event)} aria-label={`${kindLabels[event.kind]} at ${timeLabel(event)}: ${event.text ?? event.description ?? ''}`}
    aria-pressed={selected?.event_id === event.event_id} title={`${event.text ?? event.description ?? ''} · ${timeLabel(event)}`}
    onClick={() => select(event)} onKeyDown={(key) => {
      if (key.key !== 'ArrowLeft' && key.key !== 'ArrowRight') return;
      key.preventDefault();
      const sameKind = event.kind === 'on_screen_text' ? uniqueTextPoints : events.filter((item) => item.kind === event.kind);
      const index = sameKind.findIndex((item) => item.event_id === event.event_id);
      const next = sameKind[index + (key.key === 'ArrowRight' ? 1 : -1)];
      if (next) { select(next); const buttons = key.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('.timeline-mark'); buttons?.[Math.max(0, index + (key.key === 'ArrowRight' ? 1 : -1))]?.focus(); }
    }}>{!point && <span>{event.text ?? event.description}</span>}</button>;
  const timeline = <section className="m5-timeline" aria-label="Video evidence timeline">
    <div className="timeline-heading"><strong>Video timeline</strong><span>Dots: sampled observations · Bars: timed speech · Roles: interpretation</span><span>{events.length} observations</span></div>
    <div className="timeline-ruler"><span>Seek</span><div><input type="range" aria-label="Seek reference frame" min={0} max={Math.max(0, (frameTiming?.frame_count ?? 1) - 1)} value={currentFrame} disabled={!canSeek || !frameTiming} onChange={(event) => seek(Number(event.target.value))} /><div className="timeline-ticks">{Array.from({ length: 7 }, (_, index) => <span key={index}>{clock(duration * index / 6)}</span>)}</div></div></div>
    <div className="timeline-lanes">
      <div className="timeline-lane"><span>Visuals</span><div className="timeline-track">{events.filter((event) => event.kind === 'visual_action').map((event) => mark(event, true))}</div></div>
      <div className="timeline-lane"><span>Visible text <small>{groupedWords.size} groups</small></span><div className="timeline-track">{uniqueTextPoints.map((event) => mark(event, true))}</div></div>
      <div className="timeline-lane"><span>Speech</span><div className="timeline-track">{events.filter((event) => event.kind === 'speech').map((event) => mark(event, false))}</div></div>
      {events.some((event) => event.kind === 'music' || event.kind === 'sfx') && <div className="timeline-lane"><span>Other audio</span><div className="timeline-track">{events.filter((event) => event.kind === 'music' || event.kind === 'sfx').map((event) => mark(event, false))}</div></div>}
      <div className="timeline-lane"><span>Possible role</span><div className="timeline-track">{segments.map((segment) => <button type="button" className="timeline-role" key={segment.segment_id} style={{ left: positioned(segment).left }} title={`${segment.roles.map((role) => roleLabels[role]).join(', ')} · ${exactRange(segment)}`} aria-label={`Interpretation: ${segment.roles.join(', ')} at ${exactRange(segment)}`} onClick={() => { const event = events.find((item) => segment.evidence_ids.includes(item.event_id)); if (event) select(event); }}>{segment.roles[0] === 'product_demo' ? 'Product' : segment.roles[0]}</button>)}</div></div>
      {frameTiming && <div className="timeline-playhead-space" aria-hidden="true"><div className="timeline-playhead" style={{ left: `${(frameTiming.frame_boundaries_seconds[currentFrame] ?? 0) / duration * 100}%` }} /></div>}
    </div>
  </section>;
  return <>{inspectorTarget ? createPortal(inspector, inspectorTarget) : inspector}{timelineTarget ? createPortal(timeline, timelineTarget) : timeline}</>;
}
