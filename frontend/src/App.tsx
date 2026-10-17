import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react';
import type { M2Draft, TaskState } from './generated/contracts';
import { ApiError, request } from './api';
import BriefEditor, { type M2EditorStatus } from './BriefEditor';
import Directions from './Directions';
import Production from './Production';
import ReferenceWorkspace, { type WorkspaceConfig } from './ReferenceWorkspace';
import { Badge, Field, type Mutate } from './ui';
import { flushEditorDrafts } from './useEditorDraft';

const areas = [
  { id: 'inputs', title: 'Brand & task', number: '01' },
  { id: 'reference', title: 'Reference analysis', number: '02' },
  { id: 'directions', title: 'Creative directions', number: '03' },
  { id: 'production', title: 'Production & export', number: '04' },
] as const;
type Area = typeof areas[number]['id'];
function remember(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* Saved tasks remain available on the server. */ } }
function recalled(key: string) { try { return localStorage.getItem(key); } catch { return null; } }
function lastArea(taskId: string): Area {
  const saved = recalled(`video-anatomy-area:${taskId}`);
  return areas.find((area) => area.id === saved)?.id ?? 'inputs';
}
function taskProgress(state: TaskState) {
  const output = state.production_briefs.find((item) => item.output_id === state.task.current_production_brief?.id && item.revision === state.task.current_production_brief.revision);
  if (output) return output.currentness === 'current' ? 'Production ready' : 'Production needs updating';
  if (state.task.selected_direction) return 'Direction approved';
  if (state.directions.length) return 'Comparing directions';
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  if (analysis) return analysis.status === 'failed' ? 'Analysis needs attention' : analysis.review.user_confirmed ? 'Reference reviewed' : 'Reviewing reference';
  return state.task.current_video_id ? 'Reference uploaded' : state.task.current_brief ? 'Inputs applied' : 'Work in progress';
}
function savedDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(value));
}

function Workspace({ state, config, mutate, busy, onApplied, flushRef, m2Status, onStatusChange, flush, onError }: {
  state: TaskState; config: WorkspaceConfig | null; mutate: Mutate; busy: boolean;
  onApplied: (state: TaskState) => void; flushRef: RefObject<(() => Promise<M2Draft>) | null>;
  m2Status: M2EditorStatus; onStatusChange: (status: M2EditorStatus) => void;
  flush: () => Promise<void>; onError: (message: string) => void;
}) {
  const [area, setArea] = useState<Area>(() => lastArea(state.task.task_id));
  const [analysisPending, setAnalysisPending] = useState(false);
  const seekRef = useRef<((frame: number) => void) | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const brief = state.briefs.find((item) => item.brief_id === state.task.current_brief?.id && item.revision === state.task.current_brief.revision);
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  const m2Blocked = m2Status.loading || m2Status.pending || m2Status.unsaved || m2Status.legacyReviewRequired || !brief;
  const analysisBlocked = analysisPending || !analysis || analysis.status !== 'succeeded' || !analysis.review.user_confirmed;
  const selected = state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision);
  const statuses: Record<Area, string> = {
    inputs: m2Status.loading ? 'Restoring draft' : m2Status.unsaved ? 'Saving draft' : m2Status.pending ? 'Changes to apply' : brief ? 'Applied' : 'Add what you know',
    reference: analysisPending ? 'Corrections to apply' : !state.task.current_video_id ? 'Add a reference' : !analysis ? 'Ready to analyze' : analysis.status === 'failed' ? 'Needs attention' : analysis.review.user_confirmed ? 'Reviewed' : 'Review evidence',
    directions: selected?.approval_status === 'approved' && selected.currentness === 'current' ? 'Approved' : state.directions.length ? 'Compare & approve' : m2Blocked || analysisBlocked ? 'Waiting for inputs' : 'Ready to explore',
    production: state.task.current_production_brief ? taskProgress(state) : selected ? 'Ready to create' : 'After approval',
  };
  const navigate = (next: Area, focus = false) => {
    // Areas stay mounted. Let users reach an editor's recovery controls even
    // when that editor has a conflict or its autosave is temporarily failing.
    setArea(next); remember(`video-anatomy-area:${state.task.task_id}`, next);
    if (focus) window.setTimeout(() => heading.current?.focus(), 0);
    void flush().catch((failure: unknown) => onError(failure instanceof Error ? failure.message : 'Your draft could not be saved. Your text is retained; open its work area to retry.'));
  };
  useEffect(() => {
    const handleLink = (event: MouseEvent) => {
      const target = event.target instanceof Element ? event.target.closest('a[href^="#"]') : null;
      const href = target?.getAttribute('href');
      const next = areas.find((item) => `#${item.id}` === href || `#${item.id}-heading` === href)?.id;
      if (!next) return;
      event.preventDefault();
      setArea(next); remember(`video-anatomy-area:${state.task.task_id}`, next);
      void flush().catch((failure: unknown) => onError(failure instanceof Error ? failure.message : 'Could not save your draft. Your text is retained.'));
    };
    document.addEventListener('click', handleLink);
    return () => document.removeEventListener('click', handleLink);
  }, [state.task.task_id, flush, onError]);
  const seekEvidence = (frame: number) => {
    navigate('reference');
    window.requestAnimationFrame(() => seekRef.current?.(frame));
  };
  const next = m2Blocked ? { area: 'inputs' as Area, label: 'Review and apply your brand inputs' }
    : !state.task.current_video_id || analysisBlocked ? { area: 'reference' as Area, label: 'Review and confirm your reference' }
      : !state.task.selected_direction ? { area: 'directions' as Area, label: 'Compare and approve a creative direction' }
        : { area: 'production' as Area, label: 'Prepare your production materials' };
  return <>
    <section className="task-heading" aria-label="Current task"><div><p className="eyebrow">Your creative workspace</p><h1 ref={heading} tabIndex={-1}>{state.task.title}</h1><p className="task-state"><Badge warning={state.task.mode === 'sample'}>{state.task.mode === 'sample' ? 'Fictional sample task' : 'Your task'}</Badge><span>{taskProgress(state)}</span><span className="task-version">Saved version {state.task.version}</span></p></div><div className="next-step"><span className="eyebrow">Next in this task</span><button type="button" className="text-button" disabled={busy} onClick={() => navigate(next.area)}>{next.label}<span aria-hidden="true"> ↗</span></button></div></section>
    <nav className="workspace-tabs" aria-label="Workflow">{areas.map((item) => <button key={item.id} id={`tab-${item.id}`} type="button" aria-current={area === item.id ? 'page' : undefined} aria-controls={`area-${item.id}`} onClick={() => navigate(item.id)}><span className="tab-number">{item.number}</span><span><strong>{item.title}</strong><small>{statuses[item.id]}</small></span></button>)}</nav>
    <div id="area-inputs" className="workspace-area" hidden={area !== 'inputs'} aria-labelledby="tab-inputs"><BriefEditor state={state} onApplied={onApplied} flushRef={flushRef} onStatusChange={onStatusChange} busy={busy} />{state.briefs.length > 0 && <details className="history-drawer"><summary>Input history · {state.briefs.length} saved {state.briefs.length === 1 ? 'revision' : 'revisions'}</summary>{state.briefs.map((item) => <details key={`${item.brief_id}:${item.revision}`}><summary>Brand & task · revision {item.revision}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>}</div>
    <div id="area-reference" className="workspace-area" hidden={area !== 'reference'} aria-labelledby="tab-reference"><ReferenceWorkspace state={state} config={config} mutate={mutate} busy={busy} seekRef={seekRef} onPendingChange={setAnalysisPending} /></div>
    <div id="area-directions" className="workspace-area" hidden={area !== 'directions'} aria-labelledby="tab-directions">{m2Blocked && <p className="notice">Creative actions need complete, applied brand inputs. <button className="text-button" type="button" onClick={() => navigate('inputs')}>Review your inputs</button></p>}{analysisPending && <p className="notice">Reference corrections are saved as a draft. Apply and confirm them, or discard them, before new creative work.</p>}<Directions state={state} mutate={mutate} busy={busy} m2Blocked={m2Blocked || analysisPending} onSeekEvidence={seekEvidence} /></div>
    <div id="area-production" className="workspace-area" hidden={area !== 'production'} aria-labelledby="tab-production">{(m2Blocked || analysisPending) && <p className="notice">Pending input or reference changes need review before generating new production materials. Existing work remains available.</p>}<Production state={state} mutate={mutate} busy={busy} m2Blocked={m2Blocked || analysisPending} /></div>
  </>;
}

export default function App() {
  const [tasks, setTasks] = useState<TaskState[]>([]);
  const [active, setActive] = useState<TaskState | null>(null);
  const [config, setConfig] = useState<WorkspaceConfig | null>(null);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const activeId = useRef<string | null>(null);
  const flushRef = useRef<(() => Promise<M2Draft>) | null>(null);
  const [m2Status, setM2Status] = useState<M2EditorStatus>({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
  const activate = (state: TaskState) => {
    if (activeId.current !== state.task.task_id) setM2Status({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
    activeId.current = state.task.task_id;
    remember('video-anatomy-task', state.task.task_id);
    setActive((previous) => previous?.task.task_id === state.task.task_id && previous.task.version > state.task.version ? previous : state);
    setTasks((previous) => {
      const newer = previous.find((item) => item.task.task_id === state.task.task_id && item.task.version > state.task.version);
      return [newer ?? state, ...previous.filter((item) => item.task.task_id !== state.task.task_id)];
    });
  };
  const acceptApplied = (state: TaskState) => { if (activeId.current === state.task.task_id) activate(state); };
  const flush = async () => {
    await flushRef.current?.();
    if (activeId.current) await flushEditorDrafts(activeId.current);
  };
  useEffect(() => {
    let cancelled = false;
    Promise.all([request<TaskState[]>('/tasks'), request<WorkspaceConfig>('/config')]).then(([saved, settings]) => {
      if (cancelled) return;
      setTasks(saved); setConfig(settings);
      const remembered = saved.find((item) => item.task.task_id === recalled('video-anatomy-task'));
      if (remembered) activate(remembered);
    }).catch((failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'Could not connect to the backend.'); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);
  const openTask = async (id: string) => {
    setBusy(true); setError(''); setNotice('');
    try {
      await flush();
      const saved = await request<TaskState>(`/tasks/${id}`);
      // Editing stays available while loading; save any text typed during that request.
      await flush();
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
      await flush();
      const saved = await request<TaskState>(`/tasks/${taskId}${path}`, body);
      if (activeId.current === taskId) activate(saved);
      const failedJob = saved.jobs.find((job) => job.status === 'failed' && !active.jobs.some((previous) => previous.job_id === job.job_id && previous.status === 'failed'));
      if (failedJob?.error) { setError(failedJob.error.message); return false; }
      setNotice('Saved. You can reopen this task and continue where you left off.');
      return saved;
    } catch (failure) {
      setError(`${failure instanceof Error ? failure.message : 'The operation failed.'}${failure instanceof ApiError && failure.status === 409 ? ' A saved version changed. Your local draft is retained; reopen the task to review the conflict.' : ''}`);
      return false;
    } finally { setBusy(false); }
  };
  const create = async (sample = false) => {
    setBusy(true); setError(''); setNotice('');
    try {
      await flush();
      let created = await request<TaskState>('/tasks', { title: sample ? 'LumaCup · everyday moments' : title });
      if (sample) created = await request<TaskState>(`/tasks/${created.task.task_id}/sample`, { expected_version: created.task.version });
      await flush();
      if (sample) remember(`video-anatomy-area:${created.task.task_id}`, 'reference');
      activate(created); setTitle('');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not create task.'); } finally { setBusy(false); }
  };
  const createTask = (event: FormEvent) => { event.preventDefault(); void create(); };
  return <>
    <header className="app-header"><a className="wordmark" href="#" onClick={(event) => event.preventDefault()} aria-label="Video Anatomy">video anatomy<span>.</span></a><p>Observe. Consider. Create.</p><span className="header-label">Creative studio</span></header>
    <main className="app-layout">
      <aside className="task-sidebar" aria-label="Saved tasks"><div className="sidebar-heading"><h2>Your tasks</h2><span>{tasks.length.toString().padStart(2, '0')}</span></div><p className="muted sidebar-intro">A place for each idea.<br />Pick up where you left off.</p><form onSubmit={createTask}><Field label="New task title"><input required placeholder="Name your next project" value={title} onChange={(event) => setTitle(event.target.value)} disabled={busy || loading} /></Field><button type="submit" aria-label="Create task" disabled={busy || loading || !title.trim()}>＋ Create task</button></form>
        {loading ? <p role="status" className="muted">Restoring your workspace…</p> : <ul className="task-list">{tasks.map((item) => <li key={item.task.task_id}><button type="button" aria-current={active?.task.task_id === item.task.task_id ? 'page' : undefined} onClick={() => openTask(item.task.task_id)} disabled={busy}><strong>{item.task.title}</strong><small>{taskProgress(item)}</small><span className="task-date">{savedDate(item.task.updated_at)}{item.task.mode === 'sample' ? ' · Sample' : ''}</span></button></li>)}</ul>}
        {active && <button type="button" className="text-button reopen-task" disabled={busy} onClick={() => openTask(active.task.task_id)}>↻ Reopen saved task</button>}
        <div className="sidebar-note"><span className="status-dot" aria-hidden="true" /><span>Saved on this server.<br />Your tasks stay here between visits.</span></div>
      </aside>
      <div className="workspace" aria-busy={busy}>
        {error && <p role="alert" className="error">{error}</p>}
        {busy && <p role="status" className="notice global-status">Saving or processing… Your work stays in this task.</p>}
        {notice && !busy && <p role="status" className="success global-status">{notice}</p>}
        {active ? <Workspace key={active.task.task_id} state={active} config={config} mutate={mutate} busy={busy} onApplied={acceptApplied} flushRef={flushRef} m2Status={m2Status} onStatusChange={setM2Status} flush={flush} onError={setError} /> : <section className="studio-welcome"><p className="eyebrow">From reference to a considered production plan</p><h1>Great ideas start<br />with a closer look.</h1><p className="welcome-description">Bring a brand, a question, and a video worth studying. Turn what you notice into a creative direction — and a plan your team can make.</p><div className="actions"><button type="button" disabled={busy || loading} onClick={() => create(true)}>Explore the sample workspace <span aria-hidden="true">↗</span></button><span className="muted">No API key needed</span></div><div className="welcome-story"><div className="story-frame"><span className="eyebrow">A starting point</span><svg viewBox="0 0 360 240" role="img" aria-label="Abstract storyboard illustration of a cup on a sunlit table"><rect x="0" y="0" width="360" height="240" fill="#e9ded0"/><path d="M0 174 360 123v117H0z" fill="#c99e82"/><path d="m40 0 46 0 110 160-45 8zM148 0h52l116 138-45 9z" fill="#f9f0d7"/><ellipse cx="186" cy="191" rx="78" ry="14" fill="#ae7e63"/><path d="m143 71 12 111q29 19 56 0l12-111z" fill="#9d4d35"/><ellipse cx="183" cy="71" rx="40" ry="12" fill="#442e27"/><ellipse cx="183" cy="68" rx="36" ry="8" fill="#c4825c"/><path d="m166 100 6 60" stroke="#c88463" strokeWidth="5" strokeLinecap="round"/><rect x="19" y="18" width="322" height="204" fill="none" stroke="#fff8ea" strokeWidth="1"/><path d="M26 34V26h8m292 0h8v8M26 206v8h8m292 0h8v-8" fill="none" stroke="#fff8ea" strokeWidth="2"/></svg><p>One reference. Your next idea.</p></div><ol className="welcome-steps"><li><span>01</span><div><h3>Give it a purpose.</h3><p>Shape your brand and task inputs.</p></div></li><li><span>02</span><div><h3>Find the useful details.</h3><p>Review evidence, with room to correct.</p></div></li><li><span>03</span><div><h3>Make a creative choice.</h3><p>Compare two directions and approve one.</p></div></li><li><span>04</span><div><h3>Take it into production.</h3><p>Edit a brief and storyboard. Share the plan.</p></div></li></ol></div><p className="sample-disclosure">The sample uses an authored illustrated clip and fictional results. Uploaded videos require a configured provider; the sample does not establish recognition or creative quality.</p></section>}
      </div>
    </main><footer>Video Anatomy <span aria-hidden="true">/</span> A workspace for thoughtful video making <span aria-hidden="true">/</span> Single-user team demo</footer>
  </>;
}
