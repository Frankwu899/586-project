import { useEffect, useRef, useState, type FormEvent, type RefObject } from 'react';
import type { M2Draft, TaskState } from './generated/contracts';
import { ApiError, request } from './api';
import BriefEditor, { type M2EditorStatus } from './BriefEditor';
import Directions from './Directions';
import Production from './Production';
import ReferenceWorkspace, { type WorkspaceConfig } from './ReferenceWorkspace';
import StructureWorkspace from './StructureWorkspace';
import { structureApi } from './structureApi';
import { Field, type Mutate } from './ui';
import { flushEditorDrafts } from './useEditorDraft';

const areas = [{ id: 'reference', title: 'Research' }, { id: 'directions', title: 'Ideas' }, { id: 'production', title: 'Production' }] as const;
type Area = typeof areas[number]['id'];
type Activity = { taskId: string; title: string; path: string; label: string; running: boolean; error?: string; started: number; operationId?: string };
type OperationTicket = { operation_id: string; task_id: string; operation: 'recognize' | 'directions' | 'refine' | 'production'; status: 'queued' | 'running' | 'succeeded' | 'failed'; result: TaskState | null; error: { code: string; message: string } | null; created_at: string };
function scopeOf(path: string) { return path.includes('directions') || path === '/language' ? 'creative' : path.includes('outputs') ? 'production' : path === '/structure' ? 'structure' : 'reference'; }
const activityKey = (taskId: string, path: string) => `${taskId}:${scopeOf(path)}`;
const operationPaths = { recognize: '/recognize', directions: '/directions/generate', refine: '/directions/refine', production: '/outputs/generate' };
function remember(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* Server-backed drafts remain available. */ } }
function recalled(key: string) { try { return localStorage.getItem(key); } catch { return null; } }
function lastArea(taskId: string): Area { return areas.find((area) => area.id === recalled(`video-anatomy-area:${taskId}`))?.id ?? 'reference'; }
function taskProgress(state: TaskState) {
  if (state.task.current_production_brief) return 'Production saved';
  if (state.task.selected_direction) return 'Idea approved';
  if (state.directions.length) return 'Ideas saved';
  if (state.task.current_analysis) return 'Research saved';
  return state.task.current_video_id ? 'Video imported' : 'New project';
}
function actionLabel(path: string) {
  if (path === '/recognize') return 'Analyzing video';
  if (path === '/video') return 'Importing video';
  if (path.includes('/generate')) return path.includes('outputs') ? 'Preparing production' : 'Generating ideas';
  if (path.includes('/refine')) return 'Refining idea';
  if (path.includes('/approve')) return 'Approving idea';
  return 'Saving changes';
}
function ContextDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  useEffect(() => { closeRef.current = onClose; }, [onClose]);
  useEffect(() => {
    if (!open) { dialog.current?.close(); return; }
    dialog.current?.show();
    dialog.current?.querySelector<HTMLButtonElement>('button')?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); } };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [open]);
  return <dialog ref={dialog} className="context-drawer" onCancel={onClose} aria-labelledby="context-title"><div className="drawer-toolbar"><h2 id="context-title">Project context</h2><button className="secondary" type="button" onClick={onClose}>Close context</button></div><div className="drawer-content">{children}</div></dialog>;
}

function Workspace({ state, config, mutate, activities, onApplied, flushRef, m2Status, onStatusChange, flush, onError, onStructureActivity }: {
  state: TaskState; config: WorkspaceConfig | null; mutate: Mutate; activities: Activity[];
  onApplied: (state: TaskState) => void; flushRef: RefObject<(() => Promise<M2Draft>) | null>;
  m2Status: M2EditorStatus; onStatusChange: (status: M2EditorStatus) => void;
  flush: () => Promise<void>; onError: (message: string) => void;
  onStructureActivity: (running: boolean, label: string, error?: string) => void;
}) {
  const [area, setArea] = useState<Area>(() => lastArea(state.task.task_id));
  const [researchTab, setResearchTab] = useState<'timeline' | 'structure'>(() => recalled(`video-anatomy-research:${state.task.task_id}`) === 'structure' ? 'structure' : 'timeline');
  const [contextOpen, setContextOpen] = useState(false);
  const [analysisPending, setAnalysisPending] = useState(false);
  const seekRef = useRef<((frame: number) => void) | null>(null);
  const brief = state.briefs.find((item) => item.brief_id === state.task.current_brief?.id && item.revision === state.task.current_brief.revision);
  const m2Blocked = m2Status.loading || m2Status.pending || m2Status.unsaved || m2Status.legacyReviewRequired || !brief;
  const referenceBusy = activities.some((item) => item.running && scopeOf(item.path) === 'reference');
  const creativeBusy = activities.some((item) => item.running && scopeOf(item.path) === 'creative');
  const productionBusy = activities.some((item) => item.running && scopeOf(item.path) === 'production');
  const referenceError = activities.find((item) => scopeOf(item.path) === 'reference' && item.error)?.error;
  const approvedDirection = state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision);
  const navigate = (next: Area) => {
    setContextOpen(false); setArea(next); remember(`video-anatomy-area:${state.task.task_id}`, next);
    void flush().catch((failure: unknown) => onError(failure instanceof Error ? failure.message : 'Draft save failed. Your text is retained.'));
  };
  const selectResearchTab = (next: 'timeline' | 'structure') => { setResearchTab(next); remember(`video-anatomy-research:${state.task.task_id}`, next); };
  useEffect(() => {
    const handleLink = (event: MouseEvent) => {
      const href = (event.target instanceof Element ? event.target.closest('a[href^="#"]') : null)?.getAttribute('href');
      if (href === '#inputs' || href === '#inputs-heading') { event.preventDefault(); setContextOpen(true); return; }
      const next = areas.find((item) => `#${item.id}` === href || `#${item.id}-heading` === href)?.id;
      if (!next) return;
      event.preventDefault(); setContextOpen(false); setArea(next); remember(`video-anatomy-area:${state.task.task_id}`, next);
    };
    document.addEventListener('click', handleLink);
    return () => document.removeEventListener('click', handleLink);
  }, [state.task.task_id]);
  const seekEvidence = (frame: number) => {
    navigate('reference'); selectResearchTab('timeline');
    window.requestAnimationFrame(() => seekRef.current?.(frame));
  };
  const areaScope = area === 'directions' ? 'creative' : area === 'production' ? 'production' : 'reference';
  const visibleActivity = activities.filter((item) => scopeOf(item.path) === areaScope && (item.running || item.error));
  return <>
    <div className="workspace-heading"><div><h1>{state.task.title}</h1><span className="saved-state">{state.task.mode === 'sample' ? 'Fictional sample · ' : ''}Saved · v{state.task.version}</span></div><button className="secondary context-toggle" type="button" onClick={() => setContextOpen(true)}>Project context{m2Status.unsaved ? ' · Saving' : m2Status.pending ? ' · Draft' : ''}</button></div>
    <nav className="workspace-tabs" aria-label="Workspaces">{areas.map((item) => <button key={item.id} id={`tab-${item.id}`} type="button" aria-current={area === item.id ? 'page' : undefined} aria-controls={`area-${item.id}`} onClick={() => navigate(item.id)}>{item.title}</button>)}</nav>
    {visibleActivity.map((activity) => <div key={`${activity.path}:${activity.started}`} className={`workspace-feedback ${activity.error ? 'error' : 'notice'}`} role={activity.error ? 'alert' : 'status'}>{activity.running && <span className="spinner" aria-hidden="true" />}{activity.error ?? `${activity.label}… You can keep working in another area.`}</div>)}
    <div className="workspace-body">
      <div id="area-reference" className="workspace-area research-area" hidden={area !== 'reference'} aria-labelledby="tab-reference"><div className="research-tabs" role="tablist" aria-label="Research view" onKeyDown={(event) => { if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return; event.preventDefault(); const next = researchTab === 'timeline' ? 'structure' : 'timeline'; selectResearchTab(next); document.getElementById(`${next}-tab`)?.focus(); }}><button type="button" role="tab" id="timeline-tab" tabIndex={researchTab === 'timeline' ? 0 : -1} aria-selected={researchTab === 'timeline'} aria-controls="timeline-panel" onClick={() => selectResearchTab('timeline')}>Timeline</button><button type="button" role="tab" id="structure-tab" tabIndex={researchTab === 'structure' ? 0 : -1} aria-selected={researchTab === 'structure'} aria-controls="structure-panel" onClick={() => selectResearchTab('structure')}>Structure</button></div><div id="timeline-panel" role="tabpanel" aria-labelledby="timeline-tab" className="research-panel" hidden={researchTab !== 'timeline'}><ReferenceWorkspace state={state} config={config} mutate={mutate} busy={referenceBusy} actionError={referenceError} seekRef={seekRef} onPendingChange={setAnalysisPending} /></div><div id="structure-panel" role="tabpanel" aria-labelledby="structure-tab" className="research-panel" hidden={researchTab !== 'structure'}><StructureWorkspace state={state} mutate={mutate} onSeekEvidence={seekEvidence} onUseInIdeas={() => navigate('directions')} onActivity={onStructureActivity} /></div></div>
      <div id="area-directions" className="workspace-area scroll-workspace" hidden={area !== 'directions'} aria-labelledby="tab-directions">{m2Blocked && <p className="context-hint">Add brand facts when you are ready to generate. <button className="text-button" type="button" onClick={() => setContextOpen(true)}>Open project context</button></p>}<Directions state={state} mutate={mutate} busy={creativeBusy} m2Blocked={m2Blocked} analysisBlocked={analysisPending} onSeekEvidence={seekEvidence} /></div>
      <div id="area-production" className="workspace-area scroll-workspace" hidden={area !== 'production'} aria-labelledby="tab-production"><Production state={state} mutate={mutate} busy={productionBusy} m2Blocked={m2Blocked || (Boolean(approvedDirection?.analysis_ref) && analysisPending)} /></div>
    </div>
    <ContextDrawer open={contextOpen} onClose={() => setContextOpen(false)}><BriefEditor state={state} onApplied={onApplied} flushRef={flushRef} onStatusChange={onStatusChange} busy={false} />{state.briefs.length > 0 && <details className="history-drawer"><summary>Context history · {state.briefs.length} revisions</summary>{state.briefs.map((item) => <details key={`${item.brief_id}:${item.revision}`}><summary>Context revision {item.revision}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>}</ContextDrawer>
  </>;
}

export default function App() {
  const [tasks, setTasks] = useState<TaskState[]>([]);
  const [active, setActive] = useState<TaskState | null>(null);
  const [config, setConfig] = useState<WorkspaceConfig | null>(null);
  const [title, setTitle] = useState('');
  const [navigating, setNavigating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activities, setActivities] = useState<Record<string, Activity>>({});
  const [activityOpen, setActivityOpen] = useState(false);
  const activeId = useRef<string | null>(null);
  const activitiesRef = useRef(activities);
  useEffect(() => { activitiesRef.current = activities; }, [activities]);
  const pendingTasks = useRef(new Set<string>());
  const flushRef = useRef<(() => Promise<M2Draft>) | null>(null);
  const [m2Status, setM2Status] = useState<M2EditorStatus>({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
  const storeTask = (state: TaskState) => {
    setTasks((previous) => [previous.find((item) => item.task.task_id === state.task.task_id && item.task.version > state.task.version) ?? state, ...previous.filter((item) => item.task.task_id !== state.task.task_id)]);
    if (activeId.current === state.task.task_id) setActive((previous) => previous?.task.task_id === state.task.task_id && previous.task.version > state.task.version ? previous : state);
  };
  const activate = (state: TaskState) => {
    if (activeId.current !== state.task.task_id) setM2Status({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
    activeId.current = state.task.task_id; remember('video-anatomy-task', state.task.task_id); setActive((previous) => previous?.task.task_id === state.task.task_id && previous.task.version > state.task.version ? previous : state); storeTask(state);
  };
  const flush = async () => { const id = activeId.current; const saveContext = flushRef.current; if (!m2Status.loading) await saveContext?.(); if (id) await flushEditorDrafts(id); };
  useEffect(() => {
    let cancelled = false;
    Promise.all([request<TaskState[]>('/tasks'), request<WorkspaceConfig>('/config')]).then(([saved, settings]) => {
      if (cancelled) return;
      setTasks(saved); setConfig(settings);
      // Restore server jobs without restarting any provider operation.
      for (const item of saved) {
        void request<{ operations: OperationTicket[] }>(`/tasks/${item.task.task_id}/operations`).then(({ operations }) => {
          if (cancelled) return;
          for (const ticket of operations.filter((job) => ['queued', 'running'].includes(job.status))) { const path = operationPaths[ticket.operation]; const key = activityKey(item.task.task_id, path); pendingTasks.current.add(key); setActivities((previous) => ({ ...previous, [ticket.operation_id]: { taskId: item.task.task_id, title: item.task.title, path, label: actionLabel(path), running: true, started: Date.parse(ticket.created_at), operationId: ticket.operation_id } })); }
        }).catch(() => { /* Opening projects stays available if job recovery is offline. */ });
        void structureApi.get(item.task.task_id).then((structure) => {
          if (cancelled || !structure || !(['analyzing', 'researching'].includes(structure.status) || structure.feedback_status === 'running')) return;
          setActivities((previous) => ({ ...previous, [`structure:${item.task.task_id}`]: { taskId: item.task.task_id, title: item.task.title, path: '/structure', label: 'Analyzing Structure', running: true, started: Date.parse(structure.created_at) } }));
        }).catch(() => { /* Structure's own panel displays connection problems. */ });
      }
      const remembered = saved.find((item) => item.task.task_id === recalled('video-anatomy-task'));
      if (remembered) activate(remembered);
    }).catch((failure: unknown) => { if (!cancelled) setError(failure instanceof Error ? failure.message : 'Could not connect to the backend.'); }).finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // Workspace restoration is deliberately performed once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    let stopped = false; let checking = false;
    const timer = window.setInterval(async () => {
      if (checking) return;
      checking = true;
      try {
        await Promise.all(Object.entries(activitiesRef.current).filter(([, item]) => item.running && (item.operationId || item.path === '/structure')).map(async ([key, item]) => {
          try {
            if (item.operationId) {
              const ticket = await request<OperationTicket>(`/tasks/${item.taskId}/operations/${item.operationId}`);
              if (stopped || ticket.status === 'queued' || ticket.status === 'running') return;
              if (!Object.entries(activitiesRef.current).some(([otherKey, other]) => otherKey !== key && other.running && activityKey(other.taskId, other.path) === activityKey(item.taskId, item.path))) pendingTasks.current.delete(activityKey(item.taskId, item.path));
              if (ticket.result) storeTask(ticket.result);
              setActivities((previous) => ({ ...previous, [key]: { ...item, running: false, error: ticket.error?.message } }));
            } else {
              const structure = await structureApi.get(item.taskId);
              if (stopped || !structure) return;
              const isRunning = ['analyzing', 'researching'].includes(structure.status) || structure.feedback_status === 'running';
              if (!isRunning) setActivities((previous) => ({ ...previous, [key]: { ...item, running: false, error: structure.error?.message } }));
            }
          } catch { /* Leave the resumable job visible; a future poll can recover. */ }
        }));
      } finally { checking = false; }
    }, 2000);
    return () => { stopped = true; window.clearInterval(timer); };
    // Poll stable IDs and refs; changing project must not interrupt pending jobs.
  }, []);
  const openTask = async (id: string) => {
    setNavigating(true); setError('');
    try { await flush(); const saved = await request<TaskState>(`/tasks/${id}`); await flush(); activate(saved); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not reopen project.'); } finally { setNavigating(false); }
  };
  const mutate: Mutate = async (path, payload = {}) => {
    if (!active) return false;
    const snapshot = active; const taskId = snapshot.task.task_id; const key = activityKey(taskId, path);
    if (pendingTasks.current.has(key)) return false;
    pendingTasks.current.add(key);
    const operation: Activity = { taskId, title: snapshot.task.title, path, label: actionLabel(path), running: true, started: Date.now() };
    setActivities((previous) => ({ ...previous, [key]: operation }));
    let failureMessage: string | undefined;
    try {
      await flush();
      // Independent jobs may have advanced the project version. Exact input refs
      // remain in the request so changed creative evidence still fails validation.
      const latest = await request<TaskState>(`/tasks/${taskId}`);
      storeTask(latest);
      if (payload instanceof FormData) payload.set('expected_version', String(latest.task.version));
      const body = payload instanceof FormData ? payload : { ...payload, expected_version: latest.task.version };
      const saved = await request<TaskState>(`/tasks/${taskId}${path}`, body);
      storeTask(saved);
      const jobOperation = path === '/recognize' ? 'analyze' : path === '/directions/generate' ? 'directions' : path.endsWith('/refine') ? 'refine' : path === '/outputs/generate' ? 'production' : null;
      const failedJob = saved.jobs.find((job) => job.operation === jobOperation && job.status === 'failed' && !latest.jobs.some((old) => old.job_id === job.job_id && old.status === 'failed'));
      if (failedJob?.error) { failureMessage = failedJob.error.message; return false; }
      return saved;
    } catch (failure) {
      failureMessage = `${failure instanceof Error ? failure.message : 'The operation failed.'}${failure instanceof ApiError && failure.status === 409 ? ' Your draft is retained. Reopen the saved project to review the latest version.' : ''}`;
      try { storeTask(await request<TaskState>(`/tasks/${taskId}`)); } catch { /* Retain the visible draft while offline. */ }
      return false;
    } finally {
      pendingTasks.current.delete(key);
      setActivities((previous) => ({ ...previous, [key]: { ...operation, running: false, error: failureMessage } }));
    }
  };
  const create = async (sample = false) => {
    setNavigating(true); setError('');
    try {
      await flush();
      let created = await request<TaskState>('/tasks', { title: sample ? 'LumaCup · sample research' : title.trim() });
      if (sample) created = await request<TaskState>(`/tasks/${created.task.task_id}/sample`, { expected_version: created.task.version });
      await flush(); activate(created); setTitle('');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not create project.'); } finally { setNavigating(false); }
  };
  const createTask = (event: FormEvent) => { event.preventDefault(); void create(); };
  const running = Object.values(activities).filter((item) => item.running);
  const failed = Object.values(activities).filter((item) => item.error);
  return <div className="desktop-app">
    <header className="app-header"><a className="wordmark" href="#" onClick={(event) => event.preventDefault()} aria-label="Video Anatomy"><span className="brand-symbol" aria-hidden="true">◈</span> Video Anatomy</a><span className="header-label">Local workspace</span><button type="button" className={`activity-toggle secondary ${running.length ? 'has-running' : ''}`} aria-expanded={activityOpen} onClick={() => setActivityOpen(!activityOpen)}>{running.length > 0 && <span className="spinner" aria-hidden="true" />}Activity{running.length ? ` · ${running.length} running` : failed.length ? ` · ${failed.length} needs attention` : ''}</button></header>
    <main className="app-layout">
      <aside className="task-sidebar" aria-label="Saved tasks"><div className="sidebar-heading"><h2>Projects</h2><span>{tasks.length}</span></div><form onSubmit={createTask}><Field label="New task title"><input required placeholder="Project name" value={title} onChange={(event) => setTitle(event.target.value)} disabled={navigating || loading} /></Field><button type="submit" aria-label="Create task" disabled={navigating || loading || !title.trim()}>New project</button></form>
        {error && <p role="alert" className="error sidebar-error">{error}</p>}{loading ? <p role="status" className="muted">Restoring projects…</p> : <ul className="task-list">{tasks.map((item) => <li key={item.task.task_id}><button type="button" aria-current={active?.task.task_id === item.task.task_id ? 'page' : undefined} onClick={() => openTask(item.task.task_id)} disabled={navigating}><strong>{item.task.title}</strong><small>{Object.values(activities).some((operation) => operation.taskId === item.task.task_id && operation.running) ? 'Processing…' : taskProgress(item)}</small></button></li>)}</ul>}
        <div className="sidebar-bottom">{active && <button type="button" className="text-button reopen-task" disabled={navigating} onClick={() => openTask(active.task.task_id)}>Reopen saved task</button>}<p className="sidebar-note">Projects and imported files stay on this computer.</p></div>
      </aside>
      <div className="workspace">
        {active ? <Workspace key={active.task.task_id} state={active} config={config} mutate={mutate} activities={Object.values(activities).filter((item) => item.taskId === active.task.task_id)} onApplied={storeTask} flushRef={flushRef} m2Status={m2Status} onStatusChange={setM2Status} flush={flush} onError={setError} onStructureActivity={(isRunning, label, failure) => { const taskId = active.task.task_id; setActivities((previous) => { const key = `structure:${taskId}`; const old = previous[key]; if (old?.running === isRunning && old.label === label && old.error === failure) return previous; return { ...previous, [key]: { taskId, title: active.task.title, path: '/structure', label, running: isRunning, error: failure, started: old?.started ?? Date.now() } }; }); }} /> : <section className="studio-welcome"><div className="welcome-mark" aria-hidden="true">◈</div><h1>Start with a video. Or an idea.</h1><p>Create a project to research a reference, explore ideas, or prepare a production.</p><button type="button" className="secondary" disabled={navigating || loading} onClick={() => create(true)}>Explore the sample workspace</button><small>Fictional sample · no API calls</small></section>}
      </div>
    </main>
    <footer className="app-status"><span>{running.length ? `${running.length} operation${running.length === 1 ? '' : 's'} running` : 'Ready'}</span><span>Video Anatomy · Local preview</span></footer>
    {activityOpen && <section className="activity-panel" aria-label="Activity center"><div className="drawer-toolbar"><h2>Activity</h2><button className="text-button" type="button" onClick={() => setActivityOpen(false)}>Close</button></div>{Object.values(activities).length ? <ul>{Object.values(activities).map((item, index) => <li key={`${item.taskId}:${item.path}:${index}`}><strong>{item.title}</strong><p>{item.running ? <span className="spinner" aria-hidden="true" /> : null}{item.error ?? `${item.label}${item.running ? '…' : ' · Complete'}`}</p><button type="button" className="text-button" onClick={() => { void openTask(item.taskId); setActivityOpen(false); }}>Open project</button></li>)}</ul> : <p className="muted">No operations yet.</p>}</section>}
  </div>;
}
