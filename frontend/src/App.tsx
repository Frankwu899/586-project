import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type RefObject } from 'react';
import type { M2Draft, TaskState } from './generated/contracts';
import { operationErrorMessage, request } from './api';
import ApiConnection, { ApiConnectionButton, ConnectionHelp } from './ApiConnection';
import BriefEditor, { type M2EditorStatus } from './BriefEditor';
import Directions from './Directions';
import Production from './Production';
import ReferenceWorkspace, { type WorkspaceConfig } from './ReferenceWorkspace';
import StructureWorkspace from './StructureWorkspace';
import ProjectSidebar from './ProjectSidebar';
import { structureApi } from './structureApi';
import { type Mutate } from './ui';
import { flushEditorDrafts } from './useEditorDraft';
import { registerTranslations, useI18n } from './i18n';

registerTranslations({
  'Research': '研究', 'Ideas': '创意', 'Production': '制作', 'Timeline': '时间线', 'Structure': '结构',
  'Project context': '项目背景', 'Close context': '关闭项目背景', 'Workspaces': '工作区',
  'Research view': '研究视图', 'Fictional sample · ': '虚构示例 · ', 'Saved · v{version}': '已保存 · v{version}',
  ' · Saving': ' · 保存中', ' · Draft': ' · 草稿',
  '{activity}… You can keep working in another area.': '{activity}… 你可以继续使用其他模块。',
  'Add brand facts when you are ready to generate.': '准备生成时可补充品牌信息。',
  'Open project context': '打开项目背景', 'Context history · {count} revisions': '背景历史 · {count} 个版本',
  'Context revision {revision}': '背景版本 {revision}',
  'Analyzing video': '正在分析视频', 'Importing video': '正在导入视频', 'Preparing production': '正在准备制作内容',
  'Generating ideas': '正在生成创意', 'Refining idea': '正在优化创意', 'Approving idea': '正在批准创意',
  'Saving changes': '正在保存更改', 'Analyzing Structure': '正在分析结构',
  'Local workspace': '本地工作区', 'Application language': '应用语言', 'Activity': '活动',
  ' · {count} running': ' · {count} 项进行中', ' · {count} needs attention': ' · {count} 项需处理',
  'Start with a video. Or an idea.': '从视频或创意开始。',
  'Create a project to research a reference, explore ideas, or prepare a production.': '新建项目，研究参考视频、探索创意或准备制作内容。',
  'Explore the sample workspace': '探索示例工作区', 'Fictional sample · no API calls': '虚构示例 · 无需 API 调用',
  'Dismiss': '关闭提示',
  'Ready': '就绪', 'Video Anatomy · Local preview': 'Video Anatomy · 本地预览',
  '{count} operation running': '{count} 项操作进行中', '{count} operations running': '{count} 项操作进行中',
  'Activity center': '活动中心', ' · Complete': ' · 已完成', 'No operations yet.': '暂无操作。',
  'Wait for the current project operation to finish before changing this project.': '请等待当前项目操作完成后再修改项目。',
  'Draft save failed. Your text is retained.': '草稿保存失败，文本已保留。',
  'Could not connect to the backend.': '无法连接本地服务。', 'Could not reopen project.': '无法重新打开项目。',
  'Could not create project.': '无法创建项目。', 'Could not close project.': '无法关闭项目。',
  'Could not update application language.': '无法更新应用语言。', 'Could not load Trash.': '无法加载废纸篓。',
});

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
function actionLabel(path: string) {
  if (path === '/recognize') return 'Analyzing video';
  if (path === '/video') return 'Importing video';
  if (path.includes('/generate')) return path.includes('outputs') ? 'Preparing production' : 'Generating ideas';
  if (path.includes('/refine')) return 'Refining idea';
  if (path.includes('/approve')) return 'Approving idea';
  return 'Saving changes';
}
function ContextDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: React.ReactNode }) {
  const { t } = useI18n();
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
  return <dialog ref={dialog} className="context-drawer" onCancel={onClose} aria-labelledby="context-title"><div className="drawer-toolbar"><h2 id="context-title">{t('Project context')}</h2><button className="secondary" type="button" onClick={onClose}>{t('Close context')}</button></div><div className="drawer-content">{children}</div></dialog>;
}

function Workspace({ state, config, mutate, activities, onApplied, flushRef, m2Status, onStatusChange, flush, onError, onStructureActivity }: {
  state: TaskState; config: WorkspaceConfig | null; mutate: Mutate; activities: Activity[];
  onApplied: (state: TaskState) => void; flushRef: RefObject<(() => Promise<M2Draft>) | null>;
  m2Status: M2EditorStatus; onStatusChange: (status: M2EditorStatus) => void;
  flush: () => Promise<void>; onError: (message: string) => void;
  onStructureActivity: (running: boolean, label: string, error?: string) => void;
}) {
  const { t } = useI18n();
  const [area, setArea] = useState<Area>(() => lastArea(state.task.task_id));
  const [researchTab, setResearchTab] = useState<'timeline' | 'structure'>(() => recalled(`video-anatomy-research:${state.task.task_id}`) === 'structure' ? 'structure' : 'timeline');
  const [contextOpen, setContextOpen] = useState(false);
  const [analysisPending, setAnalysisPending] = useState(false);
  const [directionPending, setDirectionPending] = useState(false);
  const seekRef = useRef<((frame: number) => void) | null>(null);
  const readingRef = useRef<HTMLDivElement>(null);
  const readingPositions = useRef<Record<string, number>>({});
  const readingKey = area === 'reference' ? researchTab : area;
  useLayoutEffect(() => {
    if (readingRef.current) readingRef.current.scrollTop = readingPositions.current[readingKey] ?? 0;
  }, [readingKey]);
  const brief = state.briefs.find((item) => item.brief_id === state.task.current_brief?.id && item.revision === state.task.current_brief.revision);
  const m2Blocked = Boolean(m2Status.error) || m2Status.loading || m2Status.pending || m2Status.unsaved || m2Status.legacyReviewRequired || !brief;
  const referenceBusy = activities.some((item) => item.running && scopeOf(item.path) === 'reference');
  const creativeBusy = activities.some((item) => item.running && scopeOf(item.path) === 'creative');
  const productionBusy = activities.some((item) => item.running && scopeOf(item.path) === 'production');
  const productionGenerating = activities.some((item) => item.running && item.path === '/outputs/generate');
  const productionError = activities.find((item) => scopeOf(item.path) === 'production' && item.error)?.error;
  const correctionError = activities.find((item) => ['/analysis/correct', '/analysis/confirm'].includes(item.path) && item.error)?.error;
  const referenceError = activities.find((item) => scopeOf(item.path) === 'reference' && !['/analysis/correct', '/analysis/confirm'].includes(item.path) && item.error)?.error;
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
      if (next === 'reference') { setResearchTab('timeline'); remember(`video-anatomy-research:${state.task.task_id}`, 'timeline'); }
    };
    document.addEventListener('click', handleLink);
    return () => document.removeEventListener('click', handleLink);
  }, [state.task.task_id]);
  const seekEvidence = (frame: number) => {
    navigate('reference'); selectResearchTab('timeline');
    window.requestAnimationFrame(() => seekRef.current?.(frame));
  };
  const areaScope = area === 'directions' ? 'creative' : area === 'production' ? 'production' : researchTab === 'structure' ? 'structure' : 'reference';
  // Research panels display actionable errors beside their own controls.
  // Keep them in Activity history without stacking a second global warning.
  const visibleActivity = activities.filter((item) => scopeOf(item.path) === areaScope && areaScope === 'creative' && (item.running || item.error));
  return <>
    <div className="workspace-heading"><div><h1>{state.task.title}</h1></div><button className="secondary context-toggle" type="button" onClick={() => setContextOpen(true)}>{t('Project context')}{m2Status.unsaved ? t(' · Saving') : m2Status.pending ? t(' · Draft') : ''}</button></div>
    <nav className="workspace-tabs" aria-label={t('Workspaces')}>{areas.map((item) => <button key={item.id} id={`tab-${item.id}`} type="button" aria-current={area === item.id ? 'page' : undefined} aria-controls={`area-${item.id}`} onClick={() => navigate(item.id)}>{t(item.title)}</button>)}</nav>
    {visibleActivity.map((activity) => <div key={`${activity.path}:${activity.started}`} className={`workspace-feedback ${activity.error ? 'error' : 'notice'}`} role={activity.error ? 'alert' : 'status'}>{activity.running && <span className="spinner" aria-hidden="true" />}{activity.error ? t(activity.error) : `${t(activity.label)}…`}<ConnectionHelp message={activity.error} /></div>)}
    <div className="workspace-body" ref={readingRef} tabIndex={0} role="region" aria-label={t('Workspace content')} onScroll={(event) => { readingPositions.current[readingKey] = event.currentTarget.scrollTop; }}>
      <div id="area-reference" className="workspace-area research-area" hidden={area !== 'reference'} aria-labelledby="tab-reference"><div className="research-tabs" role="tablist" aria-label={t('Research view')} onKeyDown={(event) => { if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return; event.preventDefault(); const next = researchTab === 'timeline' ? 'structure' : 'timeline'; selectResearchTab(next); document.getElementById(`${next}-tab`)?.focus(); }}><button type="button" role="tab" id="timeline-tab" tabIndex={researchTab === 'timeline' ? 0 : -1} aria-selected={researchTab === 'timeline'} aria-controls="timeline-panel" onClick={() => selectResearchTab('timeline')}>{t('Timeline')}</button><button type="button" role="tab" id="structure-tab" tabIndex={researchTab === 'structure' ? 0 : -1} aria-selected={researchTab === 'structure'} aria-controls="structure-panel" onClick={() => selectResearchTab('structure')}>{t('Structure')}</button></div><div id="timeline-panel" role="tabpanel" aria-labelledby="timeline-tab" className="research-panel" hidden={researchTab !== 'timeline'}><ReferenceWorkspace state={state} config={config} mutate={mutate} busy={referenceBusy} actionError={referenceError} correctionError={correctionError} seekRef={seekRef} onPendingChange={setAnalysisPending} /></div><div id="structure-panel" role="tabpanel" aria-labelledby="structure-tab" className="research-panel" hidden={researchTab !== 'structure'}><StructureWorkspace state={state} mutate={mutate} onSeekEvidence={seekEvidence} onUseInIdeas={() => navigate('directions')} onActivity={onStructureActivity} /></div></div>
      <div id="area-directions" className="workspace-area scroll-workspace" hidden={area !== 'directions'} aria-labelledby="tab-directions"><Directions state={state} mutate={mutate} busy={creativeBusy} m2Blocked={m2Blocked} analysisBlocked={analysisPending} onSeekEvidence={seekEvidence} onSelectedPendingChange={setDirectionPending} /></div>
      <div id="area-production" className="workspace-area scroll-workspace" hidden={area !== 'production'} aria-labelledby="tab-production"><Production state={state} mutate={mutate} busy={productionBusy} generating={productionGenerating} actionError={productionError} contextStatus={m2Status} analysisPending={analysisPending} directionPending={directionPending} onNavigate={(target) => { if (target === 'context') setContextOpen(true); else if (target === 'ideas') navigate('directions'); else { navigate('reference'); selectResearchTab('timeline'); } }} /></div>
    </div>
    <ContextDrawer open={contextOpen} onClose={() => setContextOpen(false)}><BriefEditor state={state} onApplied={onApplied} flushRef={flushRef} onStatusChange={onStatusChange} busy={false} />{state.briefs.length > 0 && <details className="history-drawer"><summary>{t('Context history · {count} revisions', { count: state.briefs.length })}</summary>{state.briefs.map((item) => <details key={`${item.brief_id}:${item.revision}`}><summary>{t('Context revision {revision}', { revision: item.revision })}</summary><pre>{JSON.stringify(item, null, 2)}</pre></details>)}</details>}</ContextDrawer>
  </>;
}

export default function App() {
  const { t, language, setLanguage } = useI18n();
  const [tasks, setTasks] = useState<TaskState[]>([]);
  const [trashed, setTrashed] = useState<TaskState[]>([]);
  const [active, setActive] = useState<TaskState | null>(null);
  const [config, setConfig] = useState<WorkspaceConfig | null>(null);
  const [title, setTitle] = useState('');
  const [navigating, setNavigating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activities, setActivities] = useState<Record<string, Activity>>({});
  const [activityOpen, setActivityOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.matchMedia('(min-width: 1051px)').matches);
  useEffect(() => {
    const desktop = window.matchMedia('(min-width: 1051px)');
    const adaptSidebar = () => setSidebarOpen(desktop.matches);
    desktop.addEventListener('change', adaptSidebar);
    return () => desktop.removeEventListener('change', adaptSidebar);
  }, []);
  const [languagePending, setLanguagePending] = useState(false);
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
    activeId.current = state.task.task_id; remember('video-anatomy-task', state.task.task_id); setActive((previous) => previous?.task.task_id === state.task.task_id && previous.task.version > state.task.version ? previous : state); storeTask(state); if (!window.matchMedia('(min-width: 1051px)').matches) setSidebarOpen(false);
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
  const clearActive = () => {
    activeId.current = null; flushRef.current = null; remember('video-anatomy-task', ''); setActive(null);
    setM2Status({ pending: false, unsaved: false, loading: true, legacyReviewRequired: false, missing: [] });
  };
  const requireIdle = (id: string) => {
    if (Object.values(activitiesRef.current).some((item) => item.taskId === id && item.running) || [...pendingTasks.current].some((key) => key.startsWith(`${id}:`))) {
      throw new Error('Wait for the current project operation to finish before changing this project.');
    }
  };
  const closeTask = async () => {
    if (!activeId.current || navigating) return;
    setNavigating(true); setError('');
    try { requireIdle(activeId.current); await flush(); requireIdle(activeId.current); clearActive(); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not close project.'); }
    finally { setNavigating(false); }
  };
  const loadTrash = async () => {
    try { setTrashed(await request<TaskState[]>('/trash/tasks')); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not load Trash.'); }
  };
  const projectCommand = async (id: string, command: 'rename' | 'trash' | 'restore', newTitle?: string) => {
    setNavigating(true); setError('');
    try {
      requireIdle(id);
      // Saving the active editor can advance its task version. Fetch only after
      // drafts are durable so a rename or Trash action never drops recent input.
      if (activeId.current === id || command === 'restore') await flush();
      requireIdle(id);
      const latest = command === 'restore'
        ? (await request<TaskState[]>('/trash/tasks')).find((item) => item.task.task_id === id)
        : await request<TaskState>(`/tasks/${id}`);
      if (!latest) throw new Error('Could not update project.');
      const saved = await request<TaskState>(`/tasks/${id}/${command}`, { expected_version: latest.task.version, ...(command === 'rename' ? { title: newTitle } : {}) });
      if (command === 'trash') {
        setTasks((previous) => previous.filter((item) => item.task.task_id !== id));
        setTrashed((previous) => [saved, ...previous.filter((item) => item.task.task_id !== id)]);
        setActivities((previous) => Object.fromEntries(Object.entries(previous).filter(([, item]) => item.taskId !== id)));
        if (activeId.current === id) clearActive();
      } else {
        storeTask(saved);
        if (command === 'restore') {
          setTrashed((previous) => previous.filter((item) => item.task.task_id !== id));
          // Restoring may take time; preserve text typed in the current project
          // while the restore request was in flight before opening the result.
          await flush(); activate(saved);
        }
        else setActivities((previous) => Object.fromEntries(Object.entries(previous).map(([key, item]) => [key, item.taskId === id ? { ...item, title: saved.task.title } : item])));
      }
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not update project.'); throw failure; }
    finally { setNavigating(false); }
  };
  const changeLanguage = async (next: 'English' | 'Chinese') => {
    setLanguagePending(true); setError('');
    try { await setLanguage(next); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not update application language.'); }
    finally { setLanguagePending(false); }
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
      failureMessage = operationErrorMessage(failure);
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
  return <ApiConnection><div className={`desktop-app${sidebarOpen ? ' sidebar-open' : ''}`}>
    <header className="app-header"><button type="button" className="secondary sidebar-toggle" aria-label={t('Projects')} aria-expanded={sidebarOpen} aria-controls="project-sidebar" onClick={() => setSidebarOpen(!sidebarOpen)}>☰</button><a className="wordmark" href="#" onClick={(event) => event.preventDefault()} aria-label="Video Anatomy"><span className="brand-symbol" aria-hidden="true">◈</span> Video Anatomy</a><label className="app-language"><span>{t('Application language')}</span><select aria-label={t('Application language')} value={language} disabled={languagePending} onChange={(event) => { void changeLanguage(event.target.value as 'English' | 'Chinese'); }}><option value="English">English</option><option value="Chinese">中文</option></select></label><button type="button" className={`activity-toggle secondary ${running.length ? 'has-running' : ''}`} aria-expanded={activityOpen} onClick={() => setActivityOpen(!activityOpen)}>{running.length > 0 && <span className="spinner" aria-hidden="true" />}{t('Activity')}{running.length ? t(' · {count} running', { count: running.length }) : failed.length ? t(' · {count} needs attention', { count: failed.length }) : ''}</button><ApiConnectionButton /></header>
    <main className="app-layout">
      <ProjectSidebar tasks={tasks} trashed={trashed} active={active} title={title} onTitle={setTitle} loading={loading} navigating={navigating} error="" busyIds={new Set(running.map((item) => item.taskId))} onOpen={openTask} onClose={closeTask} onCreate={createTask} onLoadTrash={loadTrash} onRename={(id, nextTitle) => projectCommand(id, 'rename', nextTitle)} onTrash={(id) => projectCommand(id, 'trash')} onRestore={(id) => projectCommand(id, 'restore')} />
      <div className="workspace">
        {error && <div className="workspace-feedback error" role="alert">{t(error)}<ConnectionHelp message={error} /><button type="button" className="text-button" onClick={() => setError('')}>{t('Dismiss')}</button></div>}
        {active ? <Workspace key={active.task.task_id} state={active} config={config} mutate={mutate} activities={Object.values(activities).filter((item) => item.taskId === active.task.task_id)} onApplied={storeTask} flushRef={flushRef} m2Status={m2Status} onStatusChange={setM2Status} flush={flush} onError={setError} onStructureActivity={(isRunning, label, failure) => { const taskId = active.task.task_id; setActivities((previous) => { const key = `structure:${taskId}`; const old = previous[key]; if (old?.running === isRunning && old.label === label && old.error === failure) return previous; return { ...previous, [key]: { taskId, title: active.task.title, path: '/structure', label, running: isRunning, error: failure, started: old?.started ?? Date.now() } }; }); }} /> : <section className="studio-welcome"><div className="welcome-mark" aria-hidden="true">◈</div><h1>{t('Start with a video. Or an idea.')}</h1><p>{t('Create a project to research a reference, explore ideas, or prepare a production.')}</p><button type="button" className="secondary" disabled={navigating || loading} onClick={() => create(true)}>{t('Explore the sample workspace')}</button><small>{t('Fictional sample · no API calls')}</small></section>}
      </div>
    </main>
    {activityOpen && <section className="activity-panel" aria-label={t('Activity center')}><div className="drawer-toolbar"><h2>{t('Activity')}</h2><button className="text-button" type="button" onClick={() => setActivityOpen(false)}>{t('Close')}</button></div>{Object.values(activities).length ? <ul>{Object.values(activities).map((item, index) => <li key={`${item.taskId}:${item.path}:${index}`}><strong>{item.title}</strong><p>{item.running ? <span className="spinner" aria-hidden="true" /> : null}{item.error ? t(item.error) : `${t(item.label)}${item.running ? '…' : t(' · Complete')}`}</p><button type="button" className="text-button" onClick={() => { void openTask(item.taskId); setActivityOpen(false); }}>{t('Open project')}</button></li>)}</ul> : <p className="muted">{t('No operations yet.')}</p>}</section>}
  </div></ApiConnection>;
}
