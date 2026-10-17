import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react';
import type { TaskState } from './generated/contracts';
import AnalysisReview from './AnalysisReview';
import { Badge, Field, seconds, type Mutate } from './ui';
import { frameAtTime, frameRateLabel, frameSeekTime, frameTimecode } from './timing';
import { hasPendingEditorDrafts } from './useEditorDraft';

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

export default function ReferenceWorkspace({ state, config, mutate, busy, seekRef, onPendingChange }: {
  state: TaskState; config: WorkspaceConfig | null; mutate: Mutate; busy: boolean;
  seekRef: RefObject<((frame: number) => void) | null>;
  onPendingChange: (pending: boolean) => void;
}) {
  const player = useRef<HTMLVideoElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [sourceUrl, setSourceUrl] = useState('');
  const [mediaError, setMediaError] = useState('');
  const [actionError, setActionError] = useState('');
  const [deleting, setDeleting] = useState<string | null>(null);
  const [rerun, setRerun] = useState(false);
  const [replacing, setReplacing] = useState(false);
  const [playback, setPlayback] = useState<{ videoId: string; time: number } | null>(null);
  const video = state.videos.find((item) => item.video_id === state.task.current_video_id);
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
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
    if (hasPendingEditorDrafts(state.task.task_id)) {
      setActionError('Save or discard your pending analysis, direction, and production edits before changing the reference or running analysis again. Your drafts are retained.');
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
    if (await mutate('/video', body)) {
      setFile(null); setMediaError(''); setReplacing(false); setSourceUrl('');
      if (fileInput.current) fileInput.current.value = '';
    }
  };
  const recognize = async () => {
    if (!video || !readyForReferenceChange()) return;
    if (analysis && !rerun) { setRerun(true); return; }
    if (await mutate('/recognize', { video_id: video.video_id })) setRerun(false);
  };
  const remove = async () => {
    if (!deleting || !readyForReferenceChange()) return;
    if (await mutate(`/videos/${deleting}/delete`)) { setDeleting(null); setMediaError(''); setRerun(false); }
  };

  return <>
    <section id="reference" className="reference-workspace" aria-labelledby="reference-heading">
      <div className="workspace-section-heading"><div><p className="eyebrow">02 · Reference analysis</p><h2 id="reference-heading">Look closer.</h2><p className="muted">Understand what is there. Decide what is useful.</p></div><Badge warning={state.task.mode === 'sample'}>{state.task.mode === 'sample' ? 'Fictional sample' : 'Your reference'}</Badge></div>
      {actionError && <p role="alert" className="error">{actionError}</p>}
      <div className="reference-composition">
        <div className="reference-viewer">
          {video && !video.deleted_at ? <>
            <div className="reference-caption"><strong>{video.original_file_name ?? 'Reference media'}</strong><span>{video.duration_seconds ? seconds(video.duration_seconds) : 'Duration unknown'}</span></div>
            {video.intake_status === 'ready' ? <video key={video.video_id} ref={player} controls preload="metadata" playsInline src={`/api/tasks/${state.task.task_id}/media/${video.video_id}`} onLoadedData={() => setMediaError('')} onTimeUpdate={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onSeeked={(event) => setPlayback({ videoId: video.video_id, time: event.currentTarget.currentTime })} onError={() => setMediaError('Reference playback is unavailable. Check that the saved media still exists and this browser supports H.264/AAC.')} aria-label="Reference video player" /> : <div className="media-placeholder"><p className="error">{video.error?.message ?? 'Saved media is missing.'}</p></div>}
            {mediaError && <p role="alert" className="error">{mediaError}</p>}
            {frameTiming && currentFrame !== null && <div className="actions frame-controls" aria-label="Reference frame controls"><button type="button" className="secondary" disabled={!canSeek || currentFrame === 0} onClick={() => seek(currentFrame - 1)}>Previous frame</button><output data-testid="reference-frame-position">{frameTimecode(currentFrame, frameTiming)} · frame {currentFrame} / {frameTiming.frame_count - 1}</output><button type="button" className="secondary" disabled={!canSeek || currentFrame >= frameTiming.frame_count - 1} onClick={() => seek(currentFrame + 1)}>Next frame</button></div>}
            <div className="reference-analysis-action"><div><h3>{analysis ? 'Return to the evidence' : 'Ready when you are.'}</h3><p className="muted">{analysis ? 'Review the observations below. A new analysis preserves the previous result in history.' : 'Check playback first. Recognition starts only when you choose to analyze.'}</p></div><button disabled={busy || video.intake_status !== 'ready'} type="button" onClick={recognize}>{analysis ? 'Analyze again' : state.task.mode === 'sample' ? 'Run sample analysis' : 'Start analysis'}</button></div>
            {rerun && <div className="notice" role="region" aria-label="Confirm analysis rerun"><p>Run a new analysis? Your earlier analysis and creative work will remain in history. Review and confirm the new result before creating new directions.</p><div className="actions"><button type="button" disabled={busy} onClick={recognize}>Confirm new analysis</button><button className="secondary" type="button" onClick={() => setRerun(false)}>Cancel</button></div></div>}
            <details className="media-details"><summary>Media details and source</summary>
              <p className="muted">{video.origin.description}</p><p>{video.video_codec ?? 'Unknown codec'} · {video.has_audio === null ? 'Audio unknown' : video.has_audio ? 'Audio track present' : 'No audio track'}</p>
              {frameTiming ? <><p data-testid="source-frame-rate">Reference: {frameRateLabel(frameTiming)} · {frameTiming.frame_count} frames · {frameTiming.rate_mode === 'variable' ? 'Variable frame rate' : 'Constant frame rate'}</p><p className="muted">Timecode is HH:MM:SS:FF, non-drop-frame. Frame labels are approximate for fractional or variable rates; seeking uses measured frame timestamps.</p></> : <p className="notice">Frame timing unavailable. Upload the source video and analyze it again before using this legacy analysis.</p>}
              {video.playback && <p className="muted">Playing an H.264 browser copy. Evidence keeps original source frame numbers.</p>}
              {video.source_url && <p>Source: <a href={video.source_url} target="_blank" rel="noreferrer">{video.source_url}</a></p>}
              <p className="muted">{video.public_metrics ? `Public metrics · views: ${video.public_metrics.views ?? 'unknown'}, likes: ${video.public_metrics.likes ?? 'unknown'}, comments: ${video.public_metrics.comments ?? 'unknown'}.` : 'Public views, likes, and comments: unknown.'}</p>
            </details>
          </> : <div className="media-placeholder"><span className="film-mark" aria-hidden="true">▷</span><h3>A reference is a starting point.</h3><p>Upload a video, or explore the fictional sample.<br />You can work on your brand inputs first, too.</p></div>}
        </div>
        <div className="reference-sources"><h3>Reference sources</h3><p className="muted">One selected reference for this version. Uploaded sources and their histories stay with this task.</p>
          {state.videos.length > 0 && <ul className="source-list">{state.videos.map((item) => <li key={item.video_id} className={item.video_id === state.task.current_video_id ? 'active' : ''}><span className="source-mark" aria-hidden="true">{item.deleted_at ? '−' : '▸'}</span><div><strong>{item.original_file_name ?? 'Reference media'}</strong><small>{item.deleted_at ? 'Source media deleted · history retained' : item.video_id === state.task.current_video_id ? 'Current reference' : 'Previous reference · history retained'}</small>{!item.deleted_at && <button type="button" className="text-button" disabled={busy} onClick={() => { if (readyForReferenceChange()) setDeleting(item.video_id); }}>Delete media</button>}</div></li>)}</ul>}
          {deleting && <div className="notice" role="region" aria-label="Confirm reference deletion"><p>Delete this video and its playback copy? Historical analysis and creative work stay saved, with the source marked unavailable. Dependent approvals become historical.</p><div className="actions"><button type="button" disabled={busy} onClick={remove}>Delete reference media</button><button type="button" className="secondary" onClick={() => setDeleting(null)}>Cancel deletion</button></div></div>}
          <details open={!video}><summary>{video ? 'Upload a different reference' : 'Upload a reference file'}</summary>
            <form onSubmit={upload}><fieldset disabled={busy}><Field label="Reference video file"><input ref={fileInput} type="file" accept={config?.supported_extensions.join(',') ?? '.mp4'} required onChange={(event) => { setFile(event.target.files?.[0] ?? null); setReplacing(false); }} /></Field><Field label="Source URL (optional)" hint="Provenance only; no platform downloading."><input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} /></Field>
              {config && <p className="muted">{config.supported_extensions.join(', ')} · up to {(config.max_upload_bytes / 1024 / 1024).toFixed(0)} MiB / {config.max_duration_seconds}s. {config.supported_video_codecs.join(', ')} video.</p>}
              {replacing && <p className="notice">This file becomes the current reference. Existing analysis and creative work remain historical. Brand inputs stay unchanged.</p>}
              <button type="submit" disabled={!file}>{replacing ? 'Confirm replacement upload' : 'Upload reference'}</button>
            </fieldset></form>
          </details>
          {!state.videos.length && <div className="sample-entry"><p className="eyebrow">Try the workflow</p><h4>No API key needed.</h4><p className="muted">An illustrated clip with matched, fictional observations. It demonstrates the workflow, not real recognition.</p><button disabled={busy} type="button" className="secondary" onClick={() => mutate('/sample')}>Load synthetic sample</button><small>Keeps existing inputs. A blank task receives a fictional brief.</small></div>}
        </div>
      </div>
    </section>
    {analysis && <AnalysisReview key={`${analysis.analysis_id}:${analysis.revision}`} taskId={state.task.task_id} analysis={analysis} frameTiming={video?.video_id === analysis.video_id ? frameTiming : null} mutate={mutate} busy={busy} seek={seek} canSeek={canSeek && video?.video_id === analysis.video_id} onPendingChange={onPendingChange} />}
    {state.analyses.length > 0 && <details className="history-drawer"><summary>Analysis history · {state.analyses.length} saved {state.analyses.length === 1 ? 'revision' : 'revisions'}</summary><p className="muted">Original recognition and all applied corrections remain available.</p>{state.analyses.map((item) => <details key={`${item.analysis_id}:${item.revision}`}><summary>{item.revision === 1 ? 'Original analysis' : 'Corrected analysis'} · revision {item.revision} · {item.status}{state.videos.find((source) => source.video_id === item.video_id)?.deleted_at ? ' · Source media deleted' : ''}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>}
    {state.jobs.length > 0 && <details className="history-drawer"><summary>Processing history</summary>{state.jobs.map((job) => <p key={job.job_id}>{job.operation} · {job.status}{job.error ? ` · ${job.error.message}` : ''}</p>)}</details>}
  </>;
}
