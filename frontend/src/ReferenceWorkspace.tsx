import { useI18n } from './i18n';
import './researchTranslations';
import { useCallback, useEffect, useRef, useState, type FormEvent, type RefObject } from 'react';
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

export default function ReferenceWorkspace({ state, config, mutate, busy, seekRef, onPendingChange, actionError: externalError }: {
  state: TaskState; config: WorkspaceConfig | null; mutate: Mutate; busy: boolean;
  seekRef: RefObject<((frame: number) => void) | null>;
  onPendingChange: (pending: boolean) => void; actionError?: string;
}) {
  const { t, language } = useI18n();
  const player = useRef<HTMLVideoElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [mediaError, setMediaError] = useState('');
  const [actionError, setActionError] = useState('');
  const [operation, setOperation] = useState('');
  const [analysisPending, setAnalysisPending] = useState(false);
  const reportAnalysisPending = useCallback((pending: boolean) => { setAnalysisPending(pending); onPendingChange(pending); }, [onPendingChange]);
  const [sourcesOpen, setSourcesOpen] = useState(false);
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
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  const missingChannels = analysis ? retryableChannels(analysis) : [];
  const frameTiming = video?.frame_timing;
  const playbackTiming = video?.playback?.frame_timing ?? frameTiming;
  const currentFrame = playbackTiming ? frameAtTime(playback && playback.videoId === video?.video_id ? playback.time : 0, playbackTiming) : null;
  const canSeek = video?.intake_status === 'ready' && !video.deleted_at && Boolean(playbackTiming) && !mediaError;

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
    setOperation(t("Analyzing video…"));
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
  const shownError = externalError || actionError || (lastAnalysis?.status === 'failed' ? lastAnalysis.error?.message : '');
  const sources = <div className="reference-sources">
    <div className="reference-panel-heading"><h3>{t("Source media")}</h3>{analysis && <button type="button" className="text-button" onClick={() => setSourcesOpen(false)}>{t("Back to annotation")}</button>}</div>
    {state.videos.length > 0 && <ul className="source-list">{state.videos.map((item) => <li key={item.video_id} className={item.video_id === state.task.current_video_id ? 'active' : ''}><div><strong>{item.original_file_name ?? t("Reference media")}</strong><small>{item.deleted_at ? t("Deleted · history retained") : item.video_id === state.task.current_video_id ? t("Current reference") : t("Previous reference")}</small>{!item.deleted_at && <button type="button" className="text-button" disabled={busy} onClick={() => { if (readyForReferenceChange()) setDeleting(item.video_id); }}>{t("Delete media")}</button>}</div></li>)}</ul>}
    {deleting && <div className="notice" role="region" aria-label={t("Confirm reference deletion")}><p>{t("Delete this managed video and playback copy? Historical text remains; dependent approvals become historical.")}</p><div className="actions"><button type="button" disabled={busy} onClick={remove}>{t("Delete reference media")}</button><button type="button" className="secondary" onClick={() => setDeleting(null)}>{t("Cancel deletion")}</button></div></div>}
    <details open={!video}><summary>{video ? t("Import another reference") : t("Import a reference file")}</summary><form onSubmit={upload}><fieldset disabled={busy || Boolean(running)}><Field label={t("Reference video file")}><input ref={fileInput} type="file" accept={config?.supported_extensions.join(',') ?? '.mp4'} required onChange={(event) => { setFile(event.target.files?.[0] ?? null); setReplacing(false); }} /></Field><Field label={t("Source URL (optional)")} hint={t("Saved as provenance.")}><input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></Field>
    {config && <p className="muted">{config.supported_extensions.join(', ')} · {t("{size} MiB / {duration}s maximum.", { size: (config.max_upload_bytes / 1024 / 1024).toFixed(0), duration: config.max_duration_seconds })}</p>}
    {replacing && <p className="notice">{t("Existing analyses remain in history. This becomes the current reference.")}</p>}<button type="submit" disabled={!file}>{replacing ? t("Confirm replacement upload") : t("Upload reference")}</button></fieldset></form></details>
    {!state.videos.length && <div className="sample-entry"><p className="muted">{t("Explore an illustrated sample without an API key.")}</p><button disabled={busy} type="button" className="secondary" onClick={() => mutate('/sample')}>{t("Load synthetic sample")}</button></div>}
    {video && !video.deleted_at && <details open={Boolean(mediaError)}><summary>{t("Locate original video")}</summary><p className="muted">{t("If the managed file is missing, select the exact original. Matching bytes restore existing evidence; changed content must be imported separately.")}</p><form onSubmit={repair}><input aria-label={t("Original video to restore")} type="file" accept=".mp4" disabled={busy || Boolean(running)} onChange={(event) => setRepairFile(event.target.files?.[0] ?? null)} /><button type="submit" disabled={busy || Boolean(running) || !repairFile}>{t("Restore original file")}</button></form>{repairNotice && <p role="status">{repairNotice}</p>}</details>}
    {video && <details className="media-details"><summary>{t("File details and history")}</summary><p>{video.origin.description}</p><p>{video.video_codec ?? t("Unknown codec")} · {video.has_audio ? t("Audio present") : t("No audio")}</p>{frameTiming && <p data-testid="source-frame-rate">{frameRateLabel(frameTiming)} · {t("{count} source frames · {mode} rate", { count: frameTiming.frame_count, mode: frameTiming.rate_mode })}</p>}{video.playback && <p>{t("Browser playback copy; evidence retains original source timing.")}</p>}{video.source_url && <a href={video.source_url} target="_blank" rel="noreferrer">{t("Source link")}</a>}{state.analyses.map((item) => <details key={`${item.analysis_id}:${item.revision}`}><summary>{t("Analysis")} {item.revision === 1 ? t("original") : t("revision {revision}", { revision: item.revision })} · {item.status}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>}
  </div>;
  return <section id="reference" className="reference-workspace research-timeline" aria-label={t("Reference analysis workspace")}>
    <div className="reference-toolbar"><div><strong>{video?.original_file_name ?? t("Reference analysis")}</strong>{video?.duration_seconds && <span>{seconds(video.duration_seconds)}</span>}{state.task.mode === 'sample' && <Badge warning>{t("Fictional sample")}</Badge>}</div><div className="actions"><button type="button" className="secondary" onClick={() => setSourcesOpen((open) => !open)}>{t("Source media")}</button>{video && !video.deleted_at && <><button type="button" className="secondary" disabled={busy || state.task.mode === 'sample' || video.intake_status !== 'ready'} onClick={() => setRegionOpen(true)}>{t("Content area")}</button><button type="button" disabled={busy || Boolean(running) || video.intake_status !== 'ready'} onClick={() => void recognize(Boolean(missingChannels.length))}>{running ? <><span className="working-spinner" aria-hidden="true" />{t("Analyzing…")}</> : missingChannels.length ? t("Retry missing analysis") : analysis ? t("Analyze again") : state.task.mode === 'sample' ? t("Run sample analysis") : t("Start analysis")}</button></>}</div></div>
    {(running || shownError || rerun) && <div className="reference-operation-feedback">{running && <p className="local-operation" role="status" aria-live="polite"><span className="working-spinner" aria-hidden="true" />{running}<span>{t("You can continue in another workspace.")}</span></p>}{shownError && <p className="error" role="alert">{shownError}<ConnectionHelp message={shownError} /></p>}{rerun && !running && <div className="notice" role="region" aria-label={t("Confirm analysis rerun")}><span>{t("A new analysis keeps earlier results in history.")}</span><button type="button" disabled={busy} onClick={() => void recognize()}>{t("Confirm new analysis")}</button><button type="button" className="secondary" onClick={() => setRerun(false)}>{t("Cancel")}</button></div>}</div>}
    {analysis?.output_language && analysis.output_language !== language && <div className="notice saved-output-language">{t('Saved output is in {language}. New analysis uses the app language.', { language: t(analysis.output_language) })}</div>}
    <div className="reference-editor-grid"><div className="reference-viewer">
      {video && !video.deleted_at ? <><div className="reference-video-stage">{video.intake_status === 'ready' ? <video key={video.video_id} ref={player} controls preload="metadata" playsInline src={`/api/tasks/${state.task.task_id}/media/${video.video_id}`} onLoadedData={() => setMediaError('')} onTimeUpdate={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onSeeked={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onError={() => setMediaError(t("Playback unavailable. Check the managed source file and browser codec support."))} aria-label={t("Reference video player")} /> : <div className="media-placeholder"><p role="alert">{video.error?.message ?? t("Saved media is missing.")}</p></div>}</div>
      {mediaError && <div role="alert" className="error"><p>{mediaError}</p><button type="button" className="secondary" onClick={() => setSourcesOpen(true)}>{t("Locate original file")}</button></div>}{frameTiming && currentFrame !== null && <div className="frame-controls" aria-label={t("Reference frame controls")}><button type="button" className="secondary" disabled={!canSeek || currentFrame === 0} onClick={() => seek(currentFrame - 1)}>{t("Previous frame")}</button><output data-testid="reference-frame-position">{frameTimecode(currentFrame, frameTiming)} · {currentFrame} / {frameTiming.frame_count - 1}</output><button type="button" className="secondary" disabled={!canSeek || currentFrame >= frameTiming.frame_count - 1} onClick={() => seek(currentFrame + 1)}>{t("Next frame")}</button></div>}</> : <div className="media-placeholder"><span aria-hidden="true">▷</span><h3>{t("Research starts with a video.")}</h3><p>{t("Import a reference to explore its evidence and structure.")}</p><button type="button" className="secondary" onClick={() => setSourcesOpen(true)}>{t("Choose source media")}</button></div>}
    </div><aside className="reference-inspector">{(sourcesOpen || !video || !analysis) && sources}<div ref={setInspectorTarget} hidden={sourcesOpen || !video || !analysis} />{video && !analysis && !sourcesOpen && <p className="m5-empty">{running ? t("Analysis is running. Observations will appear here.") : t("Analyze this video to inspect its observations.")}</p>}</aside>
    <div className="reference-timeline-slot" ref={setTimelineTarget}>{!analysis && <div className="timeline-empty"><strong>{t("Video timeline")}</strong><p>{running ? t("Preparing source observations…") : t("Visual points, visible text and timed speech appear after analysis.")}</p></div>}</div></div>
    {analysis && <AnalysisReview key={`${analysis.analysis_id}:${analysis.revision}`} taskId={state.task.task_id} analysis={analysis} frameTiming={video?.video_id === analysis.video_id ? frameTiming : null} mutate={mutate} busy={busy} seek={seek} canSeek={canSeek && video?.video_id === analysis.video_id} onPendingChange={reportAnalysisPending} inspectorTarget={inspectorTarget} timelineTarget={timelineTarget} currentFrame={currentFrame ?? 0} onRetryMissing={() => void recognize(true)} />}
    {regionOpen && video && <ContentAreaEditor state={state} video={video} mutate={mutate} onClose={() => setRegionOpen(false)} />}
  </section>;
}
