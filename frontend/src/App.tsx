import { useEffect, useRef, useState } from 'react';
import type { FormEvent, RefObject } from 'react';
import type { M2Draft, TaskState } from './generated/contracts';
import { ApiError, request } from './api';
import BriefEditor, { type M2EditorStatus } from './BriefEditor';
import AnalysisReview from './AnalysisReview';
import Directions from './Directions';
import Production from './Production';
import { Badge, Field, seconds, type Mutate } from './ui';
import { frameAtTime, frameRateLabel, frameSeekTime, frameTimecode } from './timing';

interface Config {
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

function History({ state }: { state: TaskState }) {
  return <section className="panel"><h2>Saved history</h2><p className="muted">Original records and every saved content revision remain available. Currentness and approval status reflect later upstream changes.</p>
    <details><summary>Analysis originals and revisions ({state.analyses.length})</summary>{state.analyses.map((item) => <details key={`${item.analysis_id}:${item.revision}`}><summary>{item.revision === 1 ? 'Original analysis' : 'Corrected analysis'} · revision {item.revision} · {item.origin.kind} · {item.analysis_id}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>
    <details><summary>Brand/task brief revisions ({state.briefs.length})</summary>{state.briefs.map((item) => <details key={`${item.brief_id}:${item.revision}`}><summary>Brand/task brief · revision {item.revision}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>
    <details><summary>Direction revisions ({state.directions.length})</summary>{state.directions.map((item) => <details key={`${item.direction_id}:${item.revision}`}><summary>{item.core_message} · r{item.revision} · {item.currentness} · {item.approval_status}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>
    <details><summary>Production output revisions ({state.production_briefs.length + state.storyboards.length})</summary>{[...state.production_briefs, ...state.storyboards].map((item) => <details key={`${item.output_id}:${item.revision}`}><summary>{'title' in item ? 'Production brief' : 'Storyboard'} · r{item.revision} · {item.currentness}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>
    <details><summary>Processing history ({state.jobs.length})</summary>{state.jobs.map((job) => <p key={job.job_id}>{job.operation} · {job.status}{job.error ? ` · ${job.error.message}` : ''}</p>)}</details>
  </section>;
}

function Workspace({ state, config, mutate, busy, onApplied, flushRef, m2Status, onStatusChange }: {
  state: TaskState; config: Config | null; mutate: Mutate; busy: boolean;
  onApplied: (state: TaskState) => void;
  flushRef: RefObject<(() => Promise<M2Draft>) | null>;
  m2Status: M2EditorStatus; onStatusChange: (status: M2EditorStatus) => void;
}) {
  const player = useRef<HTMLVideoElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [mediaError, setMediaError] = useState('');
  const [playback, setPlayback] = useState<{ videoId: string; time: number } | null>(null);
  const brief = state.briefs.find((item) => item.brief_id === state.task.current_brief?.id && item.revision === state.task.current_brief.revision);
  const video = state.videos.find((item) => item.video_id === state.task.current_video_id);
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  const frameTiming = video?.frame_timing;
  const playbackTiming = video?.playback?.frame_timing ?? frameTiming;
  const currentFrame = playbackTiming ? frameAtTime(playback && playback.videoId === video?.video_id ? playback.time : 0, playbackTiming) : null;
  const canSeek = video?.intake_status === 'ready' && Boolean(playbackTiming) && !mediaError;
  const m2Blocked = m2Status.loading || m2Status.pending || m2Status.unsaved || m2Status.legacyReviewRequired || !brief;
  const nextAction = analysis?.status === 'failed'
    ? 'Analysis failed. Read the processing error, resolve the reported issue, and request analysis again. The dedicated synthetic sample is available in a new task.'
    : analysis?.status === 'pending' || analysis?.status === 'running' ? 'Analysis is still processing. Reopen this saved task to refresh its status.'
      : analysis?.status === 'partial' ? 'Partial analysis is not eligible for creative generation in this skeleton. Resolve failed categories and run analysis again.'
        : !brief ? 'Add what you know, or start with a reference. Apply complete inputs before creative directions.' : !video ? 'Load the dedicated sample or upload a reference.' : !analysis ? 'Run analysis for the saved reference.' : !frameTiming || analysis.frame_count === null ? 'Reference frame timing is unavailable. Upload the source video and analyze it again before confirming this legacy analysis.' : !analysis.review.user_confirmed ? 'Review observations, save any corrections, and confirm the analysis.' : m2Blocked ? 'Review and apply your input changes, or discard them, before creative actions.' : !state.task.selected_direction ? 'Compare directions and explicitly approve one.' : 'Generate or edit your production materials.';
  const seek = (frame: number) => {
    if (player.current && playbackTiming && video) {
      const time = frameSeekTime(frame, playbackTiming);
      player.current.pause();
      player.current.currentTime = time;
      setPlayback({ videoId: video.video_id, time });
    }
  };
  const stepFrame = (offset: number) => {
    if (player.current && playbackTiming) seek(frameAtTime(player.current.currentTime, playbackTiming) + offset);
  };
  const upload = async (event: FormEvent) => {
    event.preventDefault();
    if (!file) return;
    const body = new FormData();
    body.append('file', file);
    if (sourceUrl) body.append('source_url', sourceUrl);
    if (await mutate('/video', body)) { setFile(null); setMediaError(''); }
  };
  return <>
    <section className="panel"><h1>{state.task.title}</h1><p><Badge warning={state.task.mode === 'sample'}>{state.task.mode === 'sample' ? 'Fictional sample task' : video ? 'Uploaded reference task' : 'Reference not added'}</Badge><span className="muted">Saved task version {state.task.version}</span></p><p className="notice"><strong>Next:</strong> {nextAction}</p></section>
    <BriefEditor state={state} onApplied={onApplied} flushRef={flushRef} onStatusChange={onStatusChange} busy={busy} />
    <section id="reference" className="panel" aria-labelledby="reference-heading"><h2 id="reference-heading">2. Reference video</h2>
      <p className="muted">The dedicated synthetic clip has matched sample observations. Uploaded videos use the configured recognition provider; missing configuration and extraction failures are reported explicitly.</p>
      {config?.analysis_output_language && <p className="muted">Analysis descriptions: {config.analysis_output_language}. Creative drafts: {config.creative_output_language ?? 'server configuration'}. Recognized on-screen text and speech retain their source wording.</p>}
      {!state.videos.length && <div className="actions"><button disabled={busy} type="button" onClick={() => mutate('/sample')}>Load synthetic sample</button><small>Keeps your inputs; a blank task receives a fictional example.</small></div>}
      <details open={!video}><summary>Upload a reference file</summary>
        {config && <p className="muted">Supported: {config.supported_extensions.join(', ')} / {config.supported_video_codecs.join(', ')} video{config.supported_audio_codecs.length ? `; optional ${config.supported_audio_codecs.join(', ')} audio` : ''}. Limit {(config.max_upload_bytes / 1024 / 1024).toFixed(0)} MiB, {config.max_duration_seconds}s, {config.max_width}×{config.max_height}. {config.language_assumption}.</p>}
        <form onSubmit={upload}><fieldset disabled={busy}>
          <Field label="Reference video file"><input type="file" accept={config?.supported_extensions.join(',') ?? '.mp4'} required onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></Field>
          <Field label="Source URL (optional)" hint="Saved as provenance only. No platform downloading."><input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></Field>
          <button type="submit" disabled={!file}>Upload reference</button>
        </fieldset></form>
      </details>
      {video && <>
        <p><strong>{video.original_file_name ?? 'Reference media'}</strong> · {video.duration_seconds ? seconds(video.duration_seconds) : 'Duration unknown'} · {video.video_codec ?? 'Unknown codec'} · {video.has_audio === null ? 'Audio unknown' : video.has_audio ? 'Audio track present' : 'No audio track'}</p>
        {frameTiming ? <><p className="muted" data-testid="source-frame-rate">Reference: {frameRateLabel(frameTiming)} · {frameTiming.frame_count} frames · {frameTiming.rate_mode === 'variable' ? 'Variable frame rate' : 'Constant frame rate'}</p><p className="muted">Timecode is HH:MM:SS:FF, using {Math.max(1, Math.round(frameTiming.fps_numerator / frameTiming.fps_denominator))} frame labels per second (non-drop-frame). {frameTiming.rate_mode === 'variable' || frameTiming.fps_numerator % frameTiming.fps_denominator !== 0 ? 'Timecode is approximate; seeking uses the video’s measured frame timestamps.' : 'Seeking uses the video’s measured frame timestamps.'}</p></> : <p className="notice">Frame timing unavailable. Legacy seconds are preserved; upload the source video and analyze it again to use frames.</p>}
        <p className="muted">{video.origin.description}</p>
        {video.playback && <p className="muted">Playing an H.264 browser copy of the {video.video_codec} source. Evidence keeps the original source frame numbers; playback uses the copy’s measured timestamps.</p>}
        {video.intake_status === 'ready' ? <video key={video.video_id} ref={player} controls preload="metadata" playsInline src={`/api/tasks/${state.task.task_id}/media/${video.video_id}`} onLoadedData={() => setMediaError('')} onTimeUpdate={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onSeeked={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onError={() => setMediaError('Reference playback is unavailable. Check that the saved media still exists and this browser supports H.264/AAC.')} aria-label="Reference video player" /> : <p className="error">{video.error?.message ?? 'Saved media is missing.'}</p>}
        {mediaError && <p role="alert" className="error">{mediaError}</p>}
        {frameTiming && currentFrame !== null && <div className="actions" aria-label="Reference frame controls"><button type="button" className="secondary" disabled={!canSeek || currentFrame === 0} onClick={() => stepFrame(-1)}>Previous frame</button><button type="button" className="secondary" disabled={!canSeek || currentFrame >= frameTiming.frame_count - 1} onClick={() => stepFrame(1)}>Next frame</button><output data-testid="reference-frame-position">{frameTimecode(currentFrame, frameTiming)} · frame {currentFrame} / {frameTiming.frame_count - 1}</output></div>}
        <div className="actions"><button disabled={busy} type="button" onClick={() => mutate('/recognize', { video_id: video.video_id })}>{state.task.mode === 'sample' ? (analysis ? 'Rerun sample analysis (keep history)' : 'Run sample analysis') : 'Request real analysis'}</button></div>
        <p className="muted">{video.public_metrics ? `Public metrics · views: ${video.public_metrics.views ?? 'unknown'}, likes: ${video.public_metrics.likes ?? 'unknown'}, comments: ${video.public_metrics.comments ?? 'unknown'}; captured ${video.public_metrics.captured_at ?? 'date unknown'}.` : 'Public views, likes, and comments: unknown.'}</p>
      </>}
    </section>
    {analysis && <AnalysisReview key={`${analysis.analysis_id}:${analysis.revision}`} analysis={analysis} frameTiming={video?.video_id === analysis.video_id ? frameTiming : null} mutate={mutate} busy={busy} seek={seek} canSeek={canSeek && video?.video_id === analysis.video_id} />}
    {m2Blocked && <p className="notice">Creative actions require applied inputs with no pending changes. Save, review and apply your inputs, or discard changes. Reference work remains available.</p>}
    <Directions state={state} mutate={mutate} busy={busy} m2Blocked={m2Blocked} />
    <Production state={state} mutate={mutate} busy={busy} m2Blocked={m2Blocked} />
    <History state={state} />
  </>;
}

export default function App() {
  const [tasks, setTasks] = useState<TaskState[]>([]);
  const [active, setActive] = useState<TaskState | null>(null);
  const [config, setConfig] = useState<Config | null>(null);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const activeId = useRef<string | null>(null);
  const flushRef = useRef<(() => Promise<M2Draft>) | null>(null);
  const [m2Status, setM2Status] = useState<M2EditorStatus>({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
  const activate = (state: TaskState) => {
    if (activeId.current !== state.task.task_id) setM2Status({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
    activeId.current = state.task.task_id;
    localStorage.setItem('video-anatomy-task', state.task.task_id);
    setActive((previous) => previous?.task.task_id === state.task.task_id && previous.task.version > state.task.version ? previous : state);
    setTasks((previous) => {
      const newer = previous.find((item) => item.task.task_id === state.task.task_id && item.task.version > state.task.version);
      return [newer ?? state, ...previous.filter((item) => item.task.task_id !== state.task.task_id)];
    });
  };
  const acceptApplied = (state: TaskState) => {
    if (activeId.current === state.task.task_id) activate(state);
  };
  useEffect(() => {
    let cancelled = false;
    Promise.all([request<TaskState[]>('/tasks'), request<Config>('/config')]).then(([saved, settings]) => {
      if (cancelled) return;
      setTasks(saved); setConfig(settings);
      const remembered = saved.find((item) => item.task.task_id === localStorage.getItem('video-anatomy-task'));
      if (remembered) activate(remembered);
    }).catch((failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'Could not connect to the backend.'); });
    return () => { cancelled = true; };
  }, []);
  const openTask = async (id: string) => {
    setBusy(true); setError(''); setNotice('');
    try {
      await flushRef.current?.();
      const saved = await request<TaskState>(`/tasks/${id}`);
      // Editing stays available during the read; preserve text entered while it ran.
      await flushRef.current?.();
      activate(saved);
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not reopen task.'); } finally { setBusy(false); }
  };
  const mutate: Mutate = async (path, payload = {}) => {
    if (!active || busy) return false;
    const taskId = active.task.task_id;
    setBusy(true); setError(''); setNotice('');
    if (payload instanceof FormData) payload.set('expected_version', String(active.task.version));
    const body = payload instanceof FormData ? payload : { ...payload, expected_version: active.task.version };
    try {
      if (path.startsWith('/directions/') || path === '/outputs/generate') await flushRef.current?.();
      const saved = await request<TaskState>(`/tasks/${taskId}${path}`, body);
      if (activeId.current === taskId) activate(saved);
      const failedJob = saved.jobs.find((job) => job.status === 'failed' && !active.jobs.some((previous) => previous.job_id === job.job_id && previous.status === 'failed'));
      if (failedJob?.error) {
        setError(failedJob.error.message);
        return false;
      }
      setNotice('Saved. Your task can be reopened after refresh.');
      return true;
    } catch (failure) {
      setError(`${failure instanceof Error ? failure.message : 'The operation failed.'}${failure instanceof ApiError && failure.status === 409 ? ' Reopen the task to load its latest saved version; unsaved form text is retained until then.' : ''}`);
      return false;
    } finally { setBusy(false); }
  };
  const createTask = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      await flushRef.current?.();
      const created = await request<TaskState>('/tasks', { title });
      await flushRef.current?.();
      activate(created); setTitle('');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not create task.'); } finally { setBusy(false); }
  };
  return <><header><h1>video anatomy.</h1><p>From a reference to a considered production plan.</p></header><main>
    <aside>{active && <nav aria-label="Workflow" className="workflow-rail"><a href="#inputs">Inputs</a><a href="#reference">Reference</a><a href="#directions">Directions</a><a href="#production">Production</a></nav>}<h2>Tasks</h2><form onSubmit={createTask}><Field label="New task title"><input required value={title} onChange={(event) => setTitle(event.target.value)} disabled={busy} /></Field><button type="submit" disabled={busy || !title.trim()}>Create task</button></form>
      <ul>{tasks.map((item) => <li key={item.task.task_id}><button type="button" aria-current={active?.task.task_id === item.task.task_id ? 'page' : undefined} onClick={() => openTask(item.task.task_id)} disabled={busy}>{item.task.title}<small>{item.task.mode} · {item.task.progress}</small></button></li>)}</ul>
      {active && <button type="button" className="secondary" disabled={busy} onClick={() => openTask(active.task.task_id)}>Reopen saved task</button>}
    </aside>
    <div className="workspace" aria-busy={busy}>
      {error && <p role="alert" className="error">{error}</p>}
      {busy && <p role="status" className="notice">Saving or processing…</p>}
      {notice && !busy && <p role="status" className="success">{notice}</p>}
      {active ? <Workspace key={active.task.task_id} state={active} config={config} mutate={mutate} busy={busy} onApplied={acceptApplied} flushRef={flushRef} m2Status={m2Status} onStatusChange={setM2Status} /> : <section className="panel"><h2>Start a video planning task</h2><p>Create a task, add what you know, and upload a reference or load the dedicated synthetic sample.</p><p className="notice">Uploaded references use configured providers. The separate sample workflow uses fictional results. This team demonstration does not measure creative effectiveness.</p></section>}
    </div>
  </main><footer>Video Anatomy · single-user team demonstration · contract v0.5 · sample results are fictional</footer></>;
}
