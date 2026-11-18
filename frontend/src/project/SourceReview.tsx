import { useEffect, useRef, useState } from 'react';
import type { EvidenceEvent, Project, Resource, SourceRef } from './contracts';
import { Badge, FailureNotice, SupportDetails, time } from './Common';
import { fileUrl, type Mutate } from './client';
import { EvidenceEditor } from './ResourceReview';
import { playbackSeconds, sourceMapping, sourceSeconds } from './sourceTiming';
import { channelLabel, coverageMessage, evidenceOrigin, failureMessage } from './status';
import { resourceIsTrashed } from './resourceLibrary';
import SpeechModel, { type SpeechModelId } from './SpeechModel';
import './source-review.css';

const stamp = (seconds: number) => `${time(Math.max(0, seconds))}.${Math.floor((Math.max(0, seconds) % 1) * 10)}`;
const tracks = ['visual', 'on_screen_text', 'speech', 'sound'] as const;
const trackName = (kind: string) => kind === 'visual' ? 'Visual observations' : channelLabel[kind] ?? kind;
const evidenceChoice = (source: SourceRef | null) => source?.evidence_revision != null ? String(source.evidence_revision) : source?.start_seconds != null && !source.event_id ? 'source-only' : 'current';

export default function SourceReview({ project, resource, source, mutate, speechModel = 'whisper-1', onSpeechModel }: { project: Project; resource: Resource; source: SourceRef | null; mutate: Mutate; speechModel?: SpeechModelId; onSpeechModel?: (model: SpeechModelId) => void }) {
  const player = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const correctionDialog = useRef<HTMLDialogElement>(null);
  const relink = useRef<HTMLInputElement>(null);
  const [choice, setChoice] = useState(evidenceChoice(source));
  const [selectedId, setSelectedId] = useState<string | null>(source?.event_id ?? null);
  const [playhead, setPlayhead] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [query, setQuery] = useState('');
  const [playbackError, setPlaybackError] = useState('');
  const [playbackDiagnostics, setPlaybackDiagnostics] = useState<Record<string, unknown>>({});
  const [relinkRevision, setRelinkRevision] = useState(0);
  const [pending, setPending] = useState('');
  const [editing, setEditing] = useState(false);
  const [ignoreCitation, setIgnoreCitation] = useState(false);
  const latest = resource.evidence.at(-1);
  const sourceOnly = choice === 'source-only';
  const evidence = choice === 'current' ? latest : sourceOnly ? undefined : resource.evidence.find(item => String(item.revision) === choice);
  const historical = evidence && evidence.revision !== latest?.revision;
  const missingRevision = choice !== 'current' && !sourceOnly && !evidence;
  const missingEvent = Boolean(!ignoreCitation && source?.event_id && source.evidence_revision != null && choice === String(source.evidence_revision) && evidence && !evidence.events.some(item => item.id === source.event_id));
  const unversionedEvent = Boolean(!ignoreCitation && source?.event_id && source.evidence_revision == null && choice === 'current');
  const requestedEvent = evidence?.events.find(item => item.id === source?.event_id);
  const sourceTimeIssue = !ignoreCitation && source && (source.start_seconds != null || source.end_seconds != null || source.event_id) ? (() => {
    const start = source.start_seconds; const end = source.end_seconds;
    if (start == null || !Number.isFinite(start) || start < 0 || (end != null && (!Number.isFinite(end) || end < start)) || (resource.duration_seconds != null && (start > resource.duration_seconds || (end != null && end > resource.duration_seconds)))) return 'The citation timing is missing or outside the recorded source duration.';
    if (requestedEvent && (end == null || Math.abs(start - requestedEvent.start_seconds) > 1e-6 || Math.abs(end - requestedEvent.end_seconds) > 1e-6)) return 'The citation timing conflicts with its exact saved event.';
    return '';
  })() : '';
  const citationUnavailable = missingRevision || missingEvent || unversionedEvent || Boolean(sourceTimeIssue);
  const trashed = resourceIsTrashed(project, resource);
  const events = citationUnavailable ? [] : evidence?.events ?? [];
  const selected = events.find(item => item.id === selectedId);
  const duration = resource.duration_seconds;
  const mapping = sourceMapping(resource);
  const canSeek = !trashed && mapping !== 'unavailable' && duration != null && duration > 0 && !playbackError;
  const latestJob = project.jobs.filter(item => item.resource_id === resource.id).at(-1);
  const preparedJob = project.jobs.filter(item => item.resource_id === resource.id && item.kind === 'extract' && ['succeeded', 'partial'].includes(item.status)).at(-1);
  // Preparation is asynchronous and keeps the file URL stable. Replace the
  // failed media element only after a new preview has actually finished.
  const playbackKey = `${resource.id}:${resource.playback_path}:${preparedJob?.id ?? ''}:${relinkRevision}`;
  // Chromium can retain a previously decoded corrupt response by URL even
  // across new media elements. A successful local recovery gets fresh bytes.
  const playbackUrl = `${fileUrl(project.id, resource.id, 'playback')}&generation=${encodeURIComponent(`${preparedJob?.id ?? 'initial'}:${relinkRevision}`)}`;
  const busy = Boolean(pending) || project.jobs.some(item => item.resource_id === resource.id && ['queued', 'running'].includes(item.status));
  const recognizing = pending === 'recognize' || project.jobs.some(item => item.resource_id === resource.id && ['recognize', 'reference_extraction'].includes(item.kind) && ['queued', 'running'].includes(item.status));
  const needsSpeech = ['failed', 'partial', 'error'].includes(evidence?.coverage.speech ?? '') || evidence?.diagnostics.speech === 'speech_merge_conflict';
  const missingVisuals = Object.entries(evidence?.coverage ?? {}).some(([kind, state]) => ['visual', 'visual_action', 'on_screen_text'].includes(kind) && ['partial', 'failed', 'error'].includes(state));
  const changedModel = speechModel !== (latest?.diagnostics.speech_model ?? 'whisper-1');
  const speechAttempt = project.jobs.filter(item => item.resource_id === resource.id && ['recognize', 'reference_extraction'].includes(item.kind)).sort((a, b) => Date.parse(a.updated_at) - Date.parse(b.updated_at)).at(-1);
  const speechFailure = !historical && !sourceOnly && speechAttempt?.status === 'failed' && (!latest || Date.parse(speechAttempt.updated_at) >= Date.parse(latest.created_at)) ? speechAttempt : undefined;
  const savedSpeechMessage = coverageMessage('speech', evidence?.coverage.speech ?? 'not_analyzed', Boolean(evidence?.events.some(event => event.kind === 'speech')), evidence?.diagnostics.speech);
  const speechMessage = speechFailure ? failureMessage(speechFailure.error ?? 'Speech processing could not finish. Review the failure and retry.', speechFailure.error_code) : needsSpeech && evidence?.diagnostics.speech ? failureMessage(savedSpeechMessage, evidence.diagnostics.speech) : savedSpeechMessage;
  const matchingJob = project.jobs.filter(item => item.resource_id === resource.id && item.diagnostics.evidence_revision === String(evidence?.revision)).at(-1);
  const support = [{ ...matchingJob?.diagnostics, ...evidence?.diagnostics, project_id: project.id, resource_id: resource.id, evidence_revision: evidence?.revision ?? '', job_id: matchingJob?.id ?? '' }, ...(evidence?.support_details ?? []), ...(matchingJob?.support_details ?? [])];
  const attemptSupport = speechFailure ? [{ ...speechFailure.diagnostics, project_id: project.id, resource_id: resource.id, job_id: speechFailure.id, status: speechFailure.status, failure_code: speechFailure.error_code ?? '' }, ...(speechFailure.support_details ?? [])] : [];
  const origin = evidenceOrigin((evidence?.support_details ?? []).filter(item => ['transcription_chunk', 'saved_evidence_reuse'].includes(item.stage)));
  const message = playbackError || (trashed ? 'This source is in Trash. Its evidence and history are retained; restore it from Media Pool before playback.' : speechFailure || historical || sourceOnly ? null : !needsSpeech || ['missing', 'unsupported'].includes(resource.status) ? resource.error : null);
  const citationStart = source?.start_seconds;
  const citationPlaybackTime = citationStart != null && !ignoreCitation && !citationUnavailable && canSeek ? playbackSeconds(resource, citationStart) : null;
  useEffect(() => {
    setChoice(evidenceChoice(source));
    setSelectedId(source?.event_id ?? null);
    setIgnoreCitation(false);
    setPlayhead(0);
  }, [source, resource.duration_seconds]);
  useEffect(() => { heading.current?.focus(); }, [resource.id, source]);
  useEffect(() => {
    if (citationPlaybackTime != null) { if (player.current) player.current.currentTime = citationPlaybackTime; setPlayhead(citationStart ?? 0); }
  }, [source, citationPlaybackTime, citationStart]);
  useEffect(() => { if (editing) correctionDialog.current?.showModal(); }, [editing]);
  const seek = (seconds: number, event?: EvidenceEvent) => {
    setIgnoreCitation(true);
    setPlayhead(seconds); if (event) setSelectedId(event.id); else setSelectedId(null);
    if (canSeek && player.current) { player.current.pause(); player.current.currentTime = playbackSeconds(resource, seconds); }
  };
  const loadedMetadata = () => {
    setPlaybackError('');
    if (citationPlaybackTime != null && player.current) player.current.currentTime = citationPlaybackTime;
  };
  const failedPlayback = (media: HTMLMediaElement) => {
    const code = media.error?.code ?? 0;
    const names: Record<number, string> = { 1: 'MEDIA_ERR_ABORTED', 2: 'MEDIA_ERR_NETWORK', 3: 'MEDIA_ERR_DECODE', 4: 'MEDIA_ERR_SRC_NOT_SUPPORTED' };
    setPlaybackDiagnostics({
      stage: 'playback', operation: 'media_load', project_id: project.id, resource_id: resource.id,
      media_error_code: code, media_error_name: names[code] ?? 'MEDIA_ERR_UNKNOWN',
      media_network_state: media.networkState, media_ready_state: media.readyState,
      video_codec: resource.media_metadata.video_codec, audio_codec: resource.media_metadata.audio_codec,
      media_representation: resource.playback_path && resource.playback_path !== resource.original_path ? 'preview' : 'original',
      format_name: resource.media_metadata.format_name, pixel_format: resource.media_metadata.pixel_format,
      video_profile: resource.media_metadata.video_profile,
      playback_video_codec: resource.media_metadata.playback_video_codec,
      playback_pixel_format: resource.media_metadata.playback_pixel_format,
      playback_audio_codec: resource.media_metadata.playback_audio_codec,
      playback_format_name: resource.media_metadata.playback_format_name,
    });
    setPlaybackError('Playback is unavailable. Open the original to check the file, or rebuild its media preview. Saved evidence is retained.');
  };
  const operate = async (action: 'recognize' | 'extract' | 'evidence/review', transcriptionModel?: SpeechModelId) => {
    if (busy || trashed) return;
    setPending(action);
    try { await mutate(`/resources/${resource.id}/${action}`, action === 'recognize' && transcriptionModel ? { transcription_model: transcriptionModel } : {}); } finally { setPending(''); }
  };
  const ordered = [...events].sort((a, b) => a.start_seconds - b.start_seconds || a.id.localeCompare(b.id));
  const stepEvidence = (direction: -1 | 1) => {
    const position = ordered.findIndex(item => item.id === selectedId);
    const event = position >= 0 ? ordered[position + direction] : direction > 0 ? ordered.find(item => item.start_seconds > playhead) : [...ordered].reverse().find(item => item.start_seconds < playhead);
    if (event) seek(event.start_seconds, event);
  };
  const selectionLabel = selected ? `${trackName(selected.kind)} · ${stamp(selected.start_seconds)}` : `Source position · ${stamp(playhead)}`;
  const viewCurrent = () => { setChoice('current'); setSelectedId(null); setIgnoreCitation(true); };
  return <section className="va-source-review" aria-label="Source Review">
    <div className="va-page-heading"><div><span className="va-eyebrow">RESOURCES / SOURCE REVIEW</span><h1 ref={heading} tabIndex={-1}>{resource.name}</h1></div><label>Evidence revision<select aria-label="Evidence revision" value={choice} onChange={event => { setChoice(event.target.value); setSelectedId(null); setIgnoreCitation(true); }}><option value="current">Current evidence{latest ? ` · v${latest.revision}` : ''}</option>{evidenceChoice(source) === 'source-only' && <option value="source-only">Source time range · no evidence revision</option>}{resource.evidence.map(item => <option key={item.revision} value={String(item.revision)}>Saved revision {item.revision}{item.revision === latest?.revision ? ' · latest' : ' · historical'}</option>)}{missingRevision && <option value={choice}>Requested revision {choice} · unavailable</option>}</select></label></div>
    {sourceOnly && !citationUnavailable && <div className="va-notice" role="status">This link identifies only a source time range. Its saved evidence revision is unavailable; current evidence was not substituted.<button type="button" onClick={viewCurrent}>View current evidence</button></div>}
    {citationUnavailable && <div className="va-notice" role="alert">{missingRevision ? `Requested evidence revision ${choice} is unavailable.` : missingEvent ? 'The cited event is unavailable in its saved evidence revision.' : unversionedEvent ? 'This citation does not identify its evidence revision.' : sourceTimeIssue} No current or approximate event was substituted.<button type="button" onClick={viewCurrent}>View current evidence</button></div>}
    {historical && !citationUnavailable && <p className="va-notice">Showing exact historical evidence revision {evidence.revision}. Corrections to current evidence do not replace this version.<button type="button" onClick={viewCurrent}>View current evidence</button></p>}
    <div className="va-source-top"><div className="va-source-player va-resource-inspector"><div className="va-source-stage">{!trashed && (resource.kind === 'video' ? <video key={playbackKey} ref={player as React.RefObject<HTMLVideoElement>} width={typeof resource.media_metadata.width === 'number' ? resource.media_metadata.width : 1280} height={typeof resource.media_metadata.height === 'number' ? resource.media_metadata.height : 720} controls playsInline preload="metadata" src={playbackUrl} aria-label="Reference video player" onLoadedMetadata={loadedMetadata} onTimeUpdate={event => { const seconds = sourceSeconds(resource, event.currentTarget.currentTime); if (seconds != null) setPlayhead(seconds); }} onError={event => failedPlayback(event.currentTarget)} /> : <audio key={playbackKey} ref={player as React.RefObject<HTMLAudioElement>} controls preload="metadata" src={playbackUrl} aria-label="Reference audio player" onLoadedMetadata={loadedMetadata} onTimeUpdate={event => { const seconds = sourceSeconds(resource, event.currentTarget.currentTime); if (seconds != null) setPlayhead(seconds); }} onError={event => failedPlayback(event.currentTarget)} />)}</div>
      <p className="va-source-clock"><output aria-live="off">{stamp(playhead)} / {duration != null ? stamp(duration) : 'Duration unavailable'}</output><span>{mapping === 'frames' ? 'Verified frame timing' : mapping === 'seconds' ? 'Source time · frame precision unavailable' : 'Source / proxy mapping unavailable'}</span></p>
      {message && <FailureNotice message={message} code={!playbackError && !trashed ? latestJob?.error_code : undefined} diagnostics={playbackError ? playbackDiagnostics : support} />}
      {mapping === 'unavailable' && <p className="va-notice">Playback and source timing cannot be safely linked for this saved proxy. Evidence remains readable; rebuild the preview to verify the mapping.</p>}
    </div><aside className="va-source-inspector va-glass" aria-label="Selected evidence"><h2>Selected evidence</h2><Badge>{selectionLabel}</Badge>{selected ? <><p className="va-source-selected-text">{selected.text}</p><p className="va-muted">{selected.precision === 'sample' ? 'Recorded sample point; not continuous coverage.' : selected.precision === 'estimated' ? 'Estimated timing; verify against playback.' : selected.precision === 'interval' ? evidence?.diagnostics.speech_timing === 'chunk' && selected.kind === 'speech' ? 'Whole audio-chunk range; sentence and word timing are unavailable.' : 'Recorded interval.' : 'Timing precision is not recorded for this legacy event.'}</p>{selected.interpretation && <p><strong>Interpretation:</strong> {selected.interpretation}</p>}</> : <p className="va-muted">Select a saved observation or transcript result to inspect it. Moving the playhead does not invent evidence for gaps.</p>}
      {evidence && !historical && latest && !citationUnavailable && <div className="va-actions"><button type="button" disabled={busy || trashed} onClick={() => setEditing(true)}>Correct text / timing</button><button type="button" disabled={busy || trashed || latest.reviewed} onClick={() => void operate('evidence/review')}>{latest.reviewed ? 'Evidence reviewed' : 'Use reviewed evidence'}</button></div>}
      <div aria-label="Recognition summary">{origin && <p className="va-muted">{origin}</p>}{evidence?.diagnostics.speech_timing === 'chunk' && evidence.events.some(event => event.kind === 'speech' && event.precision === 'interval') && <p className="va-notice">New speech blocks use audio-chunk ranges, without word or sentence timestamps. Preserved events keep their recorded precision.</p>}{(speechFailure || (evidence && needsSpeech)) && !historical && !sourceOnly && <div className="va-source-speech-status"><p role={speechFailure ? 'alert' : undefined}>{speechMessage} Completed observations and corrections are retained.</p>{speechFailure && <SupportDetails diagnostics={attemptSupport} label="Latest attempt details" />}<button type="button" disabled={busy || trashed} onClick={() => void operate('recognize', changedModel ? speechModel : undefined)}>{recognizing ? 'Recognizing…' : changedModel ? 'Transcribe with selected model' : missingVisuals ? 'Retry missing evidence' : needsSpeech ? 'Retry missing speech' : 'Retry transcription'}</button></div>}{!historical && !sourceOnly && onSpeechModel && <><SpeechModel id={`source-speech-model-${resource.id}`} value={speechModel} onChange={onSpeechModel} disabled={busy || trashed} />{!speechFailure && (!evidence || (!needsSpeech && changedModel)) && <button type="button" disabled={busy || trashed} onClick={() => void operate('recognize', speechModel)}>{recognizing ? 'Recognizing…' : 'Transcribe with selected model'}</button>}</>}</div>
      {busy && <p role="status" className="va-assistant-working"><span className="va-spinner" />{pending === 'extract' ? 'Preparing media…' : 'Processing missing evidence… Saved results remain available.'}</p>}
    </aside></div>
    <section className="va-evidence-timeline va-glass" aria-label="Evidence timeline"><div className="va-section-heading"><div><h2>Evidence timeline</h2><p className="va-muted">Recorded tracks · visual points are samples, not complete action or shot coverage.</p></div><div className="va-actions"><button type="button" disabled={!ordered.length} onClick={() => stepEvidence(-1)}>Previous evidence</button><button type="button" disabled={!ordered.length} onClick={() => stepEvidence(1)}>Next evidence</button><button type="button" onClick={() => setZoom(1)}>Fit timeline</button><button type="button" aria-label="Zoom timeline out" disabled={zoom <= 1} onClick={() => setZoom(Math.max(1, zoom - .5))}>−</button><button type="button" aria-label="Zoom timeline in" disabled={zoom >= 6} onClick={() => setZoom(Math.min(6, zoom + .5))}>+</button></div></div>
      {duration != null && duration > 0 ? <div className="va-timeline-scroll" role="region" aria-label="Scrollable source timeline" tabIndex={0}><div className="va-timeline-canvas" style={{ inlineSize: `${zoom * 100}%` }}><div className="va-timeline-ruler"><span>Source time</span><div>{[0, .25, .5, .75, 1].map(ratio => <span key={ratio} style={{ insetInlineStart: `${ratio * 100}%` }}>{time(duration * ratio)}</span>)}</div></div><div className="va-timeline-playhead"><label htmlFor={`source-playhead-${resource.id}`}>Playhead</label><input id={`source-playhead-${resource.id}`} type="range" min={0} max={duration} step={0.01} value={Math.min(playhead, duration)} disabled={!canSeek} aria-label="Source playhead" aria-valuetext={`${stamp(playhead)} source time`} onChange={event => seek(Number(event.target.value))} /></div>
        {tracks.filter(kind => events.some(event => event.kind === kind)).map(kind => <div className="va-evidence-track" key={kind}><strong>{trackName(kind)}</strong><div className="va-evidence-track-body"><span className="va-track-playhead" aria-hidden="true" style={{ insetInlineStart: `${Math.min(100, playhead / duration * 100)}%` }} />{events.filter(event => event.kind === kind).map(event => {
          const point = event.precision === 'sample' || event.precision === 'unknown' || (event.precision === undefined && kind === 'visual');
          const width = Math.max(0, (event.end_seconds - event.start_seconds) / duration * 100);
          return <button type="button" key={event.id} className={`va-timeline-event ${point ? 'sample' : 'interval'} ${event.precision ?? 'unknown'}`} style={{ insetInlineStart: `clamp(0px, ${event.start_seconds / duration * 100}%, calc(100% - 28px))`, inlineSize: point ? '28px' : `max(28px, min(${width}%, ${100 - event.start_seconds / duration * 100}%))` }} aria-label={`${trackName(kind)} at ${stamp(event.start_seconds)}: ${event.text}`} aria-pressed={selectedId === event.id} title={`${stamp(event.start_seconds)} · ${event.text}`} onClick={() => seek(event.start_seconds, event)}>{point ? <span aria-hidden="true">●</span> : <span>{event.text}</span>}</button>;
        })}</div></div>)}
      </div></div> : <p className="va-notice">The original source duration is unavailable. Saved evidence remains readable; no timing precision was invented.</p>}
      {!events.length && <p className="va-muted">{citationUnavailable ? 'The requested evidence is unavailable.' : 'No saved tracks are available. Extract speech / visuals when you choose to analyze this source.'}</p>}
    </section>
    <section className="va-source-evidence-list va-glass"><div className="va-section-heading"><h2>Evidence and transcript</h2><label htmlFor={`transcript-search-${resource.id}`}>Search transcript</label><input id={`transcript-search-${resource.id}`} type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="Search saved speech…" /></div><ol className="va-transcript">{ordered.filter(event => !query || (event.kind === 'speech' && event.text.toLocaleLowerCase().includes(query.toLocaleLowerCase()))).map(event => <li key={event.id}><button type="button" className="va-timecode" onClick={() => seek(event.start_seconds, event)} aria-label={`Seek to ${time(event.start_seconds)}: ${event.text}`}>{stamp(event.start_seconds)}</button><div><small>{trackName(event.kind)}</small><p>{event.text}</p></div></li>)}</ol>{query && !ordered.some(event => event.kind === 'speech' && event.text.toLocaleLowerCase().includes(query.toLocaleLowerCase())) && <p>No matching saved speech.</p>}</section>
    <details className="va-source-details va-glass"><summary>Coverage, original file and recovery</summary><div>{Object.entries(evidence?.coverage ?? {}).map(([kind, coverage]) => <p key={kind}>{coverageMessage(kind, coverage, events.some(event => event.kind === kind || (kind === 'visual_action' && event.kind === 'visual')), evidence?.diagnostics[kind])}</p>)}</div>{evidence?.limitations.map((item, index) => <p key={index}>{failureMessage(item)}</p>)}{resource.warnings.map((warning, index) => <p key={index}>{warning}</p>)}<SupportDetails diagnostics={support} label="Support diagnostics" /><div className="va-inspector-actions"><button type="button" disabled={busy || trashed} onClick={() => void operate('recognize')}>{latest ? 'Retry recognition' : 'Extract speech / visuals'}</button><button type="button" disabled={busy || trashed} onClick={() => void operate('extract')}>{pending === 'extract' ? 'Preparing…' : 'Rebuild media preview'}</button><a className="va-button-link" href={fileUrl(project.id, resource.id)} target="_blank" rel="noreferrer">Open original</a><input ref={relink} className="va-sr-only" tabIndex={-1} type="file" onChange={async event => { const file = event.target.files?.[0]; if (!file) return; const body = new FormData(); body.append('file', file); if (await mutate(`/resources/${resource.id}/relink`, body)) setRelinkRevision(value => value + 1); }} /><button type="button" disabled={trashed} onClick={() => relink.current?.click()}>Relink original</button></div></details>
    <dialog ref={correctionDialog} className="va-pool-dialog va-source-correction-dialog" aria-labelledby={`correct-evidence-${resource.id}`} onClose={() => setEditing(false)}><h2 id={`correct-evidence-${resource.id}`}>Review source corrections</h2>{editing && latest && <EvidenceEditor key={`${resource.id}:${latest.revision}`} project={project} resource={resource} mutate={mutate} onClose={() => correctionDialog.current?.close()} />}</dialog>
  </section>;
}
