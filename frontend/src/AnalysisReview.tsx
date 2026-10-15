import { useState } from 'react';
import type { AnalysisResult, ContentSegment, EvidenceEvent, FrameTiming } from './generated/contracts';
import { Badge, Field, seconds, type Mutate } from './ui';
import { frameRangeLabel, frameTimecode } from './timing';

type Role = ContentSegment['roles'][number];
const roleLabels: Record<Role, string> = { hook: 'Hook', product_demo: 'Product presentation/demo', proof: 'Demonstration/result', cta: 'CTA', other: 'Other / uncertain' };

export default function AnalysisReview({ analysis, frameTiming, mutate, busy, seek, canSeek }: {
  analysis: AnalysisResult; frameTiming?: FrameTiming | null; mutate: Mutate; busy: boolean; seek: (frame: number) => void; canSeek: boolean;
}) {
  const [events, setEvents] = useState(analysis.events);
  const [segments, setSegments] = useState(analysis.segments);
  const changedEvents = events.flatMap((event, index) => {
    const previous = analysis.events[index];
    const patch: { event_id: string; text?: string | null; description?: string | null } = { event_id: event.event_id };
    if (event.text !== previous.text) patch.text = event.text;
    if (event.description !== previous.description) patch.description = event.description;
    return Object.keys(patch).length > 1 ? [patch] : [];
  });
  const changedSegments = segments.filter((segment, index) => JSON.stringify(segment.roles) !== JSON.stringify(analysis.segments[index].roles)).map(({ segment_id, roles }) => ({ segment_id, roles }));
  const dirty = changedEvents.length + changedSegments.length > 0;
  const hasFrameTiming = Boolean(frameTiming && analysis.frame_count !== null);
  const rangeLabel = (item: EvidenceEvent | ContentSegment) => {
    if (frameTiming && item.start_frame !== null && item.end_frame !== null) return frameRangeLabel(item.start_frame, item.end_frame, frameTiming);
    return item.legacy_seconds ? `${seconds(item.legacy_seconds.start_seconds)}–${seconds(item.legacy_seconds.end_seconds)} · legacy seconds; frame timing unavailable` : 'Frame timing unavailable';
  };
  const analysisRef = { id: analysis.analysis_id, revision: analysis.revision };
  const updateEvent = (id: string, field: 'text' | 'description', value: string) => setEvents((items) => items.map((event) => event.event_id === id ? { ...event, [field]: value } : event));
  const toggleRole = (id: string, role: Role) => setSegments((items) => items.map((segment) => {
    if (segment.segment_id !== id) return segment;
    const next = role === 'other' ? ['other'] : segment.roles.includes(role) ? segment.roles.filter((item) => item !== role) : [...segment.roles.filter((item) => item !== 'other'), role];
    return { ...segment, roles: (next.length ? next : ['other']) as ContentSegment['roles'] };
  }));
  const eventView = (event: EvidenceEvent) => <div className={`event ${event.lane}`} key={event.event_id}>
    <div className="event-header"><button className="time" type="button" disabled={!canSeek || event.start_frame === null} onClick={() => event.start_frame !== null && seek(event.start_frame)}>{rangeLabel(event)}</button><strong>{event.lane} · {event.kind.replaceAll('_', ' ')}</strong><small>{event.event_id}</small></div>
    {(event.kind === 'speech' || event.kind === 'on_screen_text') && <Field label={`Recognized text · ${event.event_id}`}><textarea value={event.text ?? ''} onChange={(change) => updateEvent(event.event_id, 'text', change.target.value)} /></Field>}
    {event.kind === 'visual_action' ? <Field label={`Visual description · ${event.event_id}`}><textarea value={event.description ?? ''} onChange={(change) => updateEvent(event.event_id, 'description', change.target.value)} /></Field> : event.description && <p>{event.description}</p>}
    <small>{event.source} · {event.method}{event.uncertainty ? ` · Uncertainty: ${event.uncertainty}` : ''}</small>
  </div>;
  return <section className="panel" aria-labelledby="analysis-heading">
    <h2 id="analysis-heading">3. Review reference analysis</h2>
    <p><Badge warning={analysis.origin.kind === 'sample'}>{analysis.origin.kind} evidence</Badge><Badge>{analysis.status}</Badge>Revision {analysis.revision} · {analysis.review.user_confirmed ? 'Review confirmed' : 'Awaiting your review'}</p>
    <p className="muted">{analysis.origin.description} Original extraction and all saved corrections remain in history. Reference times and media are read-only.</p>
    {hasFrameTiming ? <p className="muted">Frame numbers start at 0. Ranges [start, end) include the start frame and exclude the end frame. Storyboard suggestions use a separate clock in seconds.</p> : <p className="notice">This legacy analysis has no verified frame timing. Its saved seconds remain visible. Confirmation requires reanalyzing the source video with frame timing.</p>}
    <div className="coverage" aria-label="Analysis coverage">{Object.entries(analysis.coverage).map(([kind, status]) => <span key={kind}>{kind.replaceAll('_', ' ')}: {status.replaceAll('_', ' ')}</span>)}</div>
    <p className="muted">“Not analyzed” does not mean absent. Public performance metrics are unknown unless supplied with source context.</p>
    {analysis.error && <p role="alert" className="error">{analysis.error.message}</p>}
    {analysis.empty_result_reason && <p>{analysis.empty_result_reason}</p>}
    {analysis.status === 'succeeded' && <fieldset disabled={busy}>
      {segments.map((segment, index) => <details key={segment.segment_id}>
        <summary>Section {index + 1} · {rangeLabel(segment)} · {segment.roles.map((role) => roleLabels[role]).join(', ')} · Expand observations</summary>
        <button type="button" className="time" disabled={!canSeek || segment.start_frame === null} onClick={() => segment.start_frame !== null && seek(segment.start_frame)}>{frameTiming && segment.start_frame !== null ? `Seek to ${frameTimecode(segment.start_frame, frameTiming)} (frame ${segment.start_frame})` : 'Frame seeking unavailable'}</button>
        <fieldset><legend>Section {index + 1} roles</legend><div className="roles">{(Object.keys(roleLabels) as Role[]).map((role) => <label key={role}><input type="checkbox" checked={segment.roles.includes(role)} onChange={() => toggleRole(segment.segment_id, role)} />{roleLabels[role]}</label>)}</div></fieldset>
        {segment.interpretation && <p className="muted">Role interpretation: {segment.interpretation}</p>}
        <div className="observations">{segment.evidence_ids.map((id) => events.find((event) => event.event_id === id)).filter((event): event is EvidenceEvent => Boolean(event)).map(eventView)}</div>
      </details>)}
      {events.some((event) => !segments.some((segment) => segment.evidence_ids.includes(event.event_id))) && <details><summary>Other observations</summary>{events.filter((event) => !segments.some((segment) => segment.evidence_ids.includes(event.event_id))).map(eventView)}</details>}
      <div className="actions">
        <button type="button" disabled={!dirty} onClick={() => mutate('/analysis/correct', { analysis_ref: analysisRef, event_edits: changedEvents, segment_edits: changedSegments })}>Save analysis corrections</button>
        <button type="button" disabled={dirty || analysis.review.user_confirmed || !hasFrameTiming} onClick={() => mutate('/analysis/confirm', { analysis_ref: analysisRef })}>Use this reviewed analysis</button>
      </div>
      {dirty && <p className="muted">Save corrections before confirming this revision.</p>}
      <p className="muted">Confirmation allows creative planning; it does not certify every observation as accurate.</p>
    </fieldset>}
  </section>;
}
