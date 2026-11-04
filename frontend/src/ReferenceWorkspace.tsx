import { useI18n } from './i18n';
import './researchTranslations';
import { useCallback, useEffect, useRef, useState, type CSSProperties, type FormEvent, type RefObject } from 'react';
import type { TaskState } from './generated/contracts';
import AnalysisReview from './AnalysisReview';
import { retryableChannels } from './AnalysisCoverage';
import ContentAreaEditor from './ContentAreaEditor';
import { ConnectionHelp } from './ApiConnection';
import './m5.css';
import { Badge, Field, seconds, type Mutate } from './ui';
import { frameAtTime, frameRateLabel, frameSeekTime, frameTimecode } from './timing';

export interface WorkspaceConfig {
  max_upload_bytes: number;
  max_duration_seconds: number;
  max_width: number;
  max_height: number;
  supported_extensions: string[];
  supported_video_codecs: string[];
  supported_audio_codecs: string[];
  language_assumption: string;
  analysis_output_language?: string;
  creative_output_language?: string;
}

export default function ReferenceWorkspace({ state, config, mutate, busy, seekRef, onPendingChange, actionError: externalError, correctionError }: {
  state: TaskState; config: WorkspaceConfig | null; mutate: Mutate; busy: boolean;
  seekRef: RefObject<((frame: number) => void) | null>;
  onPendingChange: (pending: boolean) => void; actionError?: string; correctionError?: string;
}) {
  const { t, language } = useI18n();
  const player = useRef<HTMLVideoElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [mediaError, setMediaError] = useState('');
  const [playbackLoading, setPlaybackLoading] = useState(false);
  const [actionError, setActionError] = useState('');
  const [operation, setOperation] = useState('');
  const [analysisPending, setAnalysisPending] = useState(false);
  const reportAnalysisPending = useCallback((pending: boolean) => { setAnalysisPending(pending); onPendingChange(pending); }, [onPendingChange]);
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [inspectorWidth, setInspectorWidth] = useState(360);
  const resizeStart = useRef<{ x: number; width: number } | null>(null);
  const [repairFile, setRepairFile] = useState<File | null>(null);
  const [repairNotice, setRepairNotice] = useState('');
  const [regionOpen, setRegionOpen] = useState(false);
  const [inspectorTarget, setInspectorTarget] = useState<HTMLDivElement | null>(null);
  const [timelineTarget, setTimelineTarget] = useState<HTMLDivElement | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);
  const [rerun, setRerun] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [playback, setPlayback] = useState<{ videoId: string; time: number } | null>(null);
  const video = state.videos.find((item) => item.video_id === state.task.current_video_id);
  const latestAnalysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  // A failed rerun must not replace useful evidence with an empty canvas.
  const analysis = latestAnalysis?.status === 'failed'
    ? [...state.analyses].reverse().find((item) => item.video_id === latestAnalysis.video_id && item.events.length > 0 && ['succeeded', 'partial'].includes(item.status)) ?? latestAnalysis
    : latestAnalysis;
  const historicalAnalysis = Boolean(analysis && analysis !== latestAnalysis);
  const missingChannels = latestAnalysis ? retryableChannels(latestAnalysis) : [];
  const frameTiming = video?.frame_timing;
  const playbackTiming = video?.playback?.frame_timing ?? frameTiming;
  const currentFrame = playbackTiming ? frameAtTime(playback && playback.videoId === video?.video_id ? playback.time : 0, playbackTiming) : null;
  const canSeek = video?.intake_status === 'ready' && !video.deleted_at && Boolean(playbackTiming) && !mediaError;
  const showSources = () => { setSourcesOpen(true); setInspectorOpen(true); };
  const showAnnotation = () => { setSourcesOpen(false); setInspectorOpen(true); };
  const resizeInspector = (width: number) => setInspectorWidth(Math.max(280, Math.min(520, width)));

  const seek = (frame: number) => {
    if (player.current && playbackTiming && video && canSeek) {
      const time = frameSeekTime(frame, playbackTiming);
      player.current.pause();
      player.current.currentTime = time;
      setPlayback({ videoId: video.video_id, time });
    }
  };
  useEffect(() => {
    seekRef.current = (frame) => {
      if (!player.current || !playbackTiming || !video || !canSeek) return;
      const time = frameSeekTime(frame, playbackTiming);
      player.current.pause(); player.current.currentTime = time;
      setPlayback({ videoId: video.video_id, time });
      player.current.scrollIntoView({ block: 'nearest', behavior: 'auto' });
    };
    return () => { seekRef.current = null; };
  }, [seekRef, playbackTiming, video, canSeek]);

  const readyForReferenceChange = () => {
    setActionError('');
    if (analysisPending) {
      setActionError(t("Save or discard the pending analysis corrections before changing the reference or analyzing again. Your drafts are retained."));
      return false;
    }
    return true;
  };
  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file || !readyForReferenceChange()) return;
    if (video && !replacing) { setReplacing(true); return; }
    const body = new FormData(); body.append('file', file);
    if (sourceUrl) body.append('source_url', sourceUrl);
    setOperation(t("Importing video…"));
    const result = await mutate('/video', body); setOperation('');
    if (result) {
      setFile(null); setMediaError(''); setReplacing(false); setSourceUrl('');
      if (fileInput.current) fileInput.current.value = '';
      setSourcesOpen(false);
    }
  };
  const recognize = async (retryMissing = false) => {
    if (!video || !readyForReferenceChange()) return;
    if (analysis && !rerun && !retryMissing) { setRerun(true); return; }
    setActionError(''); setRerun(false); setOperation(t("Analyzing video…"));
    const result = await mutate('/recognize', { video_id: video.video_id }); setOperation('');
    if (result) setRerun(false);
    else setActionError(t("Analysis could not complete. Previous results and source video are retained."));
  };
  const remove = async () => {
    if (!deleting || !readyForReferenceChange()) return;
    if (await mutate(`/videos/${deleting}/delete`)) { setDeleting(null); setMediaError(''); setRerun(false); }
  };

  const repair = async (event: FormEvent) => {
    event.preventDefault();
    if (!video || !repairFile) return;
    setOperation(t("Locating original video…")); setActionError(''); setRepairNotice('');
    const body = new FormData(); body.append('file', repairFile);
    try {
      const result = await mutate(`/videos/${video.video_id}/relink`, body);
      if (result) { setRepairFile(null); setMediaError(''); setRepairNotice(t("Original file restored. Existing analysis and drafts are retained.")); player.current?.load(); }
      else setActionError(t("The original could not be restored. Select the exact original file; different content must be imported as a new reference."));
    } finally { setOperation(''); }
  };
  const currentJob = [...state.jobs].reverse().find((job) => job.operation === 'analyze' && (job.status === 'running' || job.status === 'pending'));
  const running = operation || (currentJob ? t("Analyzing video…") : '');
  const lastAnalysis = [...state.jobs].reverse().find((job) => job.operation === 'analyze');
  const playbackProblem = mediaError || (video && !video.deleted_at && video.intake_status !== 'ready' ? video.error?.message ?? t('Saved media is missing.') : '');
  const statusText = running || (playbackLoading ? t('Loading video…') : '');
  const shownError = running ? '' : playbackProblem || externalError || actionError || (lastAnalysis?.status === 'failed' && lastAnalysis.video_id === video?.video_id ? lastAnalysis.error?.message : '') || latestAnalysis?.error?.message;
  const sources = <div className="reference-sources">
    <div className="reference-panel-heading"><h3>{t("Source media")}</h3>{analysis && <button type="button" className="text-button" onClick={() => setSourcesOpen(false)}>{t("Back to annotation")}</button>}</div>
    {state.videos.length > 0 && <ul className="source-list">{state.videos.map((item) => <li key={item.video_id} className={item.video_id === state.task.current_video_id ? 'active' : ''}><div><strong>{item.original_file_name ?? t("Reference media")}</strong><small>{item.deleted_at ? t("Deleted · history retained") : item.video_id === state.task.current_video_id ? t("Current reference") : t("Previous reference")}</small>{!item.deleted_at && <button type="button" className="text-button" disabled={busy} onClick={() => { if (readyForReferenceChange()) setDeleting(item.video_id); }}>{t("Delete media")}</button>}</div></li>)}</ul>}
    {deleting && <div className="notice" role="region" aria-label={t("Confirm reference deletion")}><p>{t("Delete this managed video and playback copy? Historical text remains; dependent approvals become historical.")}</p><div className="actions"><button type="button" disabled={busy} onClick={remove}>{t("Delete reference media")}</button><button type="button" className="secondary" onClick={() => setDeleting(null)}>{t("Cancel deletion")}</button></div></div>}
    <details open={!video}><summary>{video ? t("Import another reference") : t("Import a reference file")}</summary><form onSubmit={upload}><fieldset disabled={busy || Boolean(running)}><Field label={t("Reference video file")}><input ref={fileInput} type="file" accept={config?.supported_extensions.join(',') ?? '.mp4'} required onChange={(event) => { setFile(event.target.files?.[0] ?? null); setReplacing(false); }} /></Field><Field label={t("Source URL (optional)")}><input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></Field>
    {config && <p className="muted">{config.supported_extensions.join(', ')} · {t("{size} MiB / {duration}s maximum.", { size: (config.max_upload_bytes / 1024 / 1024).toFixed(0), duration: config.max_duration_seconds })}</p>}
    {replacing && <p className="notice">{t("Existing analyses remain in history. This becomes the current reference.")}</p>}<button type="submit" disabled={!file}>{replacing ? t("Confirm replacement upload") : t("Upload reference")}</button></fieldset></form></details>
    {video && !video.deleted_at && <details open={Boolean(mediaError)}><summary>{t("Locate original video")}</summary><p className="muted">{t("If the managed file is missing, select the exact original. Matching bytes restore existing evidence; changed content must be imported separately.")}</p><form onSubmit={repair}><input aria-label={t("Original video to restore")} type="file" accept=".mp4" disabled={busy || Boolean(running)} onChange={(event) => setRepairFile(event.target.files?.[0] ?? null)} /><button type="submit" disabled={busy || Boolean(running) || !repairFile}>{t("Restore original file")}</button></form>{repairNotice && <p role="status">{repairNotice}</p>}</details>}
    {video && <details className="media-details"><summary>{t("File details and history")}</summary><p>{video.origin.description}</p><p>{video.video_codec ?? t("Unknown codec")} · {video.has_audio ? t("Audio present") : t("No audio")}</p>{frameTiming && <p data-testid="source-frame-rate">{frameRateLabel(frameTiming)} · {t("{count} source frames · {mode} rate", { count: frameTiming.frame_count, mode: frameTiming.rate_mode })}</p>}{video.playback && <p>{t("Browser playback copy; evidence retains original source timing.")}</p>}{video.source_url && <a href={video.source_url} target="_blank" rel="noreferrer">{t("Source link")}</a>}{state.analyses.map((item) => <details key={`${item.analysis_id}:${item.revision}`}><summary>{t("Analysis")} {item.revision === 1 ? t("original") : t("revision {revision}", { revision: item.revision })} · {item.status}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>}
  </div>;
  const showInspector = inspectorOpen && (sourcesOpen || Boolean(analysis));
  return <section id="reference" className={`reference-workspace research-timeline reading-timeline${showInspector ? '' : ' inspector-closed'}${video ? '' : ' without-video'}`} aria-label={t("Reference analysis workspace")} style={{ '--reference-inspector-width': `${inspectorWidth}px` } as CSSProperties}>
    <div className="reference-toolbar">
      <div><strong>{video?.original_file_name ?? t("Timeline")}</strong>{video?.duration_seconds && <span>{seconds(video.duration_seconds)}</span>}{state.task.mode === 'sample' && <Badge warning>{t("Fictional sample")}</Badge>}</div>
      <div className="actions">
        <button type="button" className="secondary" aria-expanded={sourcesOpen && showInspector} aria-controls="reference-inspector" onClick={() => sourcesOpen && showInspector ? setSourcesOpen(false) : showSources()}>{t("Source media")}</button>
        {analysis && <button type="button" className="text-button" aria-expanded={showInspector} aria-controls="reference-inspector" onClick={() => showInspector ? setInspectorOpen(false) : showAnnotation()}>{showInspector ? t("Hide details") : t("Show details")}</button>}
        {video && !video.deleted_at && <>
          <button type="button" className="secondary" disabled={busy || state.task.mode === 'sample' || video.intake_status !== 'ready'} onClick={() => setRegionOpen(true)}>{t("Content area")}</button>
          <button type="button" disabled={busy || Boolean(running) || video.intake_status !== 'ready'} onClick={() => void recognize(Boolean(missingChannels.length))}>{missingChannels.length ? t("Retry missing analysis") : analysis ? t("Analyze again") : state.task.mode === 'sample' ? t("Run sample analysis") : t("Start analysis")}</button>
        </>}
      </div>
    </div>
    {(statusText || shownError || rerun) && <div className="reference-operation-feedback">
      {statusText && <p className="local-operation" role="status" aria-live="polite" aria-atomic="true"><span className="working-spinner" aria-hidden="true" />{statusText}</p>}
      {shownError && <div className="error" role="alert"><span>{shownError}</span><ConnectionHelp message={shownError} />{playbackProblem && <button type="button" className="text-button" onClick={showSources}>{t("Locate original file")}</button>}{analysisPending && <button type="button" className="text-button" onClick={showAnnotation}>{t("Review corrections")}</button>}</div>}
      {rerun && !running && <div className="notice" role="region" aria-label={t("Confirm analysis rerun")}><span>{t("A new analysis keeps earlier results in history.")}</span><button type="button" disabled={busy} onClick={() => void recognize()}>{t("Confirm new analysis")}</button><button type="button" className="secondary" onClick={() => setRerun(false)}>{t("Cancel")}</button></div>}
    </div>}
    {analysis?.output_language && analysis.output_language !== language && <p className="reference-language-note">{t('Saved output is in {language}. New analysis uses the app language.', { language: t(analysis.output_language) })}</p>}
    {historicalAnalysis && <p className="reference-history-note">{t("Showing previous analysis · read only")}</p>}
    <div className="reference-editor-grid">
      <div className="reference-viewer">
        {video && !video.deleted_at ? <>
          <div className="reference-video-stage">{video.intake_status === 'ready' ? <video key={video.video_id} ref={player} controls preload="metadata" playsInline src={`/api/tasks/${state.task.task_id}/media/${video.video_id}`} onLoadStart={() => setPlaybackLoading(true)} onLoadedMetadata={() => setPlaybackLoading(false)} onLoadedData={() => { setMediaError(''); setPlaybackLoading(false); }} onTimeUpdate={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onSeeked={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onError={() => { setPlaybackLoading(false); setMediaError(t("Playback unavailable. Check the managed source file and browser codec support.")); }} aria-label={t("Reference video player")} /> : <div className="media-placeholder"><span aria-hidden="true">▷</span><button type="button" className="secondary" onClick={showSources}>{t("Locate original file")}</button></div>}</div>
          {frameTiming && currentFrame !== null && <div className="frame-controls" aria-label={t("Reference frame controls")}><button type="button" className="secondary" disabled={!canSeek || currentFrame === 0} onClick={() => seek(currentFrame - 1)}>{t("Previous frame")}</button><output data-testid="reference-frame-position">{frameTimecode(currentFrame, frameTiming)} · {currentFrame} / {frameTiming.frame_count - 1}</output><button type="button" className="secondary" disabled={!canSeek || currentFrame >= frameTiming.frame_count - 1} onClick={() => seek(currentFrame + 1)}>{t("Next frame")}</button></div>}
        </> : <div className="media-placeholder"><span aria-hidden="true">▷</span><button type="button" onClick={showSources} disabled={Boolean(running)}>{t("Import video")}</button>{!state.videos.length && <button disabled={busy} type="button" className="text-button" onClick={() => mutate('/sample')}>{t("Load synthetic sample")}</button>}</div>}
      </div>
      <div className="reference-timeline-slot" ref={setTimelineTarget} hidden={!video}>{!analysis && <div className={`timeline-empty${running ? ' timeline-loading' : ''}`} aria-hidden={Boolean(running)}>{running ? <div className="timeline-skeleton"><i /><i /><i /></div> : <p>{t("No analysis yet.")}</p>}</div>}</div>
      <aside id="reference-inspector" className="reference-inspector" hidden={!showInspector}>
        <div className="reference-resize-handle" role="separator" tabIndex={0} aria-label={t("Resize evidence panel")} aria-orientation="vertical" aria-valuemin={280} aria-valuemax={520} aria-valuenow={inspectorWidth} onDoubleClick={() => setInspectorWidth(360)} onKeyDown={(event) => { if (!['ArrowLeft', 'ArrowRight', 'Home'].includes(event.key)) return; event.preventDefault(); resizeInspector(event.key === 'Home' ? 360 : inspectorWidth + (event.key === 'ArrowLeft' ? 20 : -20)); }} onPointerDown={(event) => { resizeStart.current = { x: event.clientX, width: inspectorWidth }; event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={(event) => { if (resizeStart.current) resizeInspector(resizeStart.current.width + resizeStart.current.x - event.clientX); }} onPointerUp={() => { resizeStart.current = null; }} onPointerCancel={() => { resizeStart.current = null; }} />
        <div className="reference-inspector-content">{sourcesOpen && sources}<div ref={setInspectorTarget} hidden={sourcesOpen || !analysis} /></div>
      </aside>
    </div>
    {analysis && <AnalysisReview key={`${analysis.analysis_id}:${analysis.revision}`} taskId={state.task.task_id} analysis={analysis} frameTiming={video?.video_id === analysis.video_id ? frameTiming : null} mutate={mutate} busy={busy} seek={seek} canSeek={canSeek && video?.video_id === analysis.video_id} onPendingChange={reportAnalysisPending} inspectorTarget={inspectorTarget} timelineTarget={timelineTarget} currentFrame={currentFrame ?? 0} onRetryMissing={() => void recognize(true)} onSelect={showAnnotation} readOnly={historicalAnalysis} externalActionError={correctionError} />}
    {regionOpen && video && <ContentAreaEditor state={state} video={video} mutate={mutate} onClose={() => setRegionOpen(false)} />}
  </section>;
}
