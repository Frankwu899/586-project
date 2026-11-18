import { useCallback, useEffect, useRef, useState } from 'react';
import type { Project } from './contracts';
import { failureMessage } from './status';
import { folderIsTrashed } from './resourceLibrary';

const LAST_PROJECT = 'video-anatomy:current-project';
const RECENT_PROJECTS = 'video-anatomy:recent-projects';
export function recentProjectOpenings(): Record<string, string> {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(RECENT_PROJECTS) ?? '{}');
    if (saved && typeof saved === 'object' && !Array.isArray(saved)) {
      return Object.fromEntries(Object.entries(saved).filter(([, value]) => typeof value === 'string' && !Number.isNaN(Date.parse(value))));
    }
  } catch { /* Library records remain usable without browser preferences. */ }
  return {};
}
function rememberProject(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set('project', id); else url.searchParams.delete('project');
  window.history.replaceState(null, '', url);
  try {
    if (id) {
      localStorage.setItem(LAST_PROJECT, id);
      const recent = { ...recentProjectOpenings(), [id]: new Date().toISOString() };
      localStorage.setItem(RECENT_PROJECTS, JSON.stringify(Object.fromEntries(Object.entries(recent).sort((a, b) => b[1].localeCompare(a[1])).slice(0, 100))));
    } else localStorage.removeItem(LAST_PROJECT);
  } catch { /* URL still preserves tab refresh. */ }
}

export class ProjectError extends Error {
  constructor(message: string, public status: number, public code?: string) { super(message); }
}

export async function call<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const file = body instanceof FormData;
  const response = await fetch(`/api/projects${path}`, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: body !== undefined && !file ? { 'Content-Type': 'application/json' } : undefined,
    body: body === undefined ? undefined : file ? body : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const error = data.error ?? data.detail;
    const raw = typeof error === 'string' ? error : error?.message ?? 'The operation could not be completed.';
    const message = error?.code === 'validation_error' && /^body\.title:/.test(raw) ? 'Enter a name between 1 and 200 characters.' : failureMessage(raw, error?.code);
    throw new ProjectError(message, response.status, error?.code);
  }
  return data as T;
}

export type Mutate = (path: string, body?: Record<string, unknown> | FormData, method?: string, options?: { localError?: boolean; onError?: (message: string) => void }) => Promise<Project | null>;
const draftFlushers = new Map<string, Map<string, () => Promise<boolean>>>();
async function flushProjectDrafts(projectId: string | undefined) {
  if (!projectId) return true;
  const results = await Promise.all([...draftFlushers.get(projectId)?.values() ?? []].map(flush => flush()));
  return results.every(Boolean);
}

export function useProjectController() {
  const [project, setProject] = useState<Project | null>(null);
  const current = useRef<Project | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(0);
  const [loading, setLoading] = useState(true);
  const queue = useRef<Promise<unknown>>(Promise.resolve());
  const accept = useCallback((next: Project) => {
    if (current.current?.id === next.id && current.current.version > next.version) return;
    current.current = next; setProject(next);
  }, []);
  const refreshList = useCallback(async () => {
    try { const [active, trash] = await Promise.all([call<Project[]>(''), call<Project[]>('?trashed=true')]); setProjects([...active, ...trash]); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not load projects.'); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { void refreshList(); }, [refreshList]);
  useEffect(() => {
    const report = () => setError('A saved draft changed in another window. Your local text is retained; review it before choosing the saved version.');
    window.addEventListener('va-draft-conflict', report);
    return () => window.removeEventListener('va-draft-conflict', report);
  }, []);
  const open = useCallback(async (id: string) => {
    const saved = await flushProjectDrafts(current.current?.id);
    await queue.current;
    setError('');
    try { accept(await call<Project>(`/${id}`)); rememberProject(id); if (!saved) setError('Some edits could not be saved to the project. Their local drafts are retained for recovery.'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not open project.'); }
  }, [accept]);
  useEffect(() => {
    let id = new URL(window.location.href).searchParams.get('project');
    if (!id) { try { id = localStorage.getItem(LAST_PROJECT); } catch { /* Use dashboard. */ } }
    if (id) void open(id);
  }, [open]);
  const close = useCallback(async () => {
    const saved = await flushProjectDrafts(current.current?.id);
    await queue.current;
    current.current = null; setProject(null); rememberProject(null); void refreshList();
    if (!saved) setError('Some edits could not be saved to the project. Their local drafts are retained; reopen the project to review them.');
  }, [refreshList]);
  const mutate = useCallback<Mutate>((path, body = {}, method, options) => {
    const projectId = current.current?.id;
    if (!projectId) return Promise.resolve(null);
    setSaving(value => value + 1);
    const operation = queue.current.then(async () => {
      let baseline: Project | null = null;
      let payload: Record<string, unknown> | FormData = body;
      try {
        const latest = current.current?.id === projectId ? current.current : await call<Project>(`/${projectId}`);
        if (!latest) return null;
        baseline = latest;
        if (body instanceof FormData) { payload = body; payload.set('expected_version', String(latest.version)); }
        else payload = { ...body, expected_version: latest.version };
        const next = await call<Project>(`/${projectId}${path}`, payload, method);
        if (current.current?.id === projectId) accept(next);
        setError(''); return next;
      } catch (failure) {
        let message = failure instanceof Error ? failure.message : 'Could not save. Your draft is retained.';
        if (failure instanceof ProjectError && failure.status === 409 && /(?:version_conflict|draft_conflict)/.test(failure.code ?? '')) {
          try {
            const fresh = await call<Project>(`/${projectId}`);
            if (current.current?.id === projectId) accept(fresh);
            const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
            let safe = false;
            if (body instanceof FormData && path === '/resources' && (!method || method === 'POST') && /^(?:project_)?version_conflict$/.test(failure.code ?? '')) {
              // A 409 at new-file import occurs before resource admission; the
              // server removes any staged bytes if its final version check loses.
              // Retry this one fresh import only, never relink/replace or a
              // network failure whose admission outcome could be unknown.
              const requested = body.get('folder_id');
              const folderId = typeof requested === 'string' && requested ? requested : body.get('role') === 'document' ? 'folder_documents' : 'folder_inbox';
              if (!folderIsTrashed(fresh, folderId)) {
                body.set('expected_version', String(fresh.version));
                const imported = await call<Project>(`/${projectId}${path}`, body, method);
                if (current.current?.id === projectId) accept(imported);
                setError(''); return imported;
              }
            }
            if (baseline && !(body instanceof FormData)) {
              if (path === '' && method === 'PATCH' && failure.code === 'project_version_conflict') {
                const expected = body.expected_editor_versions as Record<string, number> | undefined;
                safe = Object.keys(body).every(key => {
                  if (key === 'expected_editor_versions') return true;
                  if (key === 'editor_drafts') return Object.keys(body.editor_drafts as Record<string, unknown>).every(scope =>
                    same(baseline!.editor_drafts[scope], fresh.editor_drafts[scope])
                    && (expected?.[scope] === undefined || expected[scope] === (fresh.editor_draft_versions[scope] ?? 0)));
                  return same(baseline![key as keyof Project], fresh[key as keyof Project]);
                });
                // Preserve the original editor preconditions on the retry.
                // Aggregate-only background changes do not own this draft.
                if (expected) safe = safe && Object.entries(expected).every(([scope, version]) => version === (fresh.editor_draft_versions[scope] ?? 0));
              }
              if (path === '/brief/draft' && !/draft.*conflict/.test(failure.code ?? '')) safe = same(baseline.brief_draft, fresh.brief_draft);
              if (path === '/selection' && failure.code === 'project_version_conflict') {
                const scope = typeof body.content_id === 'string' ? body.content_id : null;
                const previousTarget = scope ? baseline.contents.find(item => item.id === scope) : baseline;
                const freshTarget = scope ? fresh.contents.find(item => item.id === scope && !item.trashed_at) : fresh;
                safe = Boolean(previousTarget && freshTarget && same(previousTarget.selection, freshTarget.selection)
                  && Array.isArray(body.resource_ids) && body.resource_ids.every(id => fresh.resources.some(resource =>
                    resource.id === id && ['video', 'audio'].includes(resource.kind) && !resource.trashed_at
                    && !folderIsTrashed(fresh, resource.folder_id))));
              }
              // Job admission can advance the aggregate between click and save.
              // Only retry Stop for its exact saved attempt, never a newer retry.
              const stop = path.match(/^\/messages\/([^/]+)\/stop$/);
              if (stop && failure.code === 'project_version_conflict' && typeof body.attempt_id === 'string') {
                safe = fresh.jobs.some(job => job.kind === 'conversation' && job.message_id === stop[1] && job.attempt_id === body.attempt_id);
              }
            }
            if (safe && !(payload instanceof FormData)) {
              const retried = await call<Project>(`/${projectId}${path}`, { ...payload, expected_version: fresh.version }, method);
              if (current.current?.id === projectId) accept(retried);
              setError(''); return retried;
            }
            message = 'This project changed while saving. Your draft is retained. Review the latest saved content before applying it.';
          } catch (recoveryFailure) { if (recoveryFailure instanceof Error) message = recoveryFailure.message; }
        }
        options?.onError?.(message);
        if (!options?.localError) setError(message);
        return null;
      } finally { setSaving(value => value - 1); }
    });
    queue.current = operation;
    return operation;
  }, [accept]);
  useEffect(() => {
    if (!project) return;
    const id = project.id;
    const timer = window.setInterval(() => {
      if (saving) return;
      void call<Project>(`/${id}`).then(next => { if (current.current?.id === id) accept(next); }).catch(() => { /* A direct action exposes connection errors. */ });
    }, 1800);
    return () => window.clearInterval(timer);
  }, [project?.id, saving, accept]); // eslint-disable-line react-hooks/exhaustive-deps
  return { project, projects, error, setError, saving, loading, open, close, mutate, accept, refreshList };
}

export function fileUrl(projectId: string, resourceId: string, representation = 'original') {
  return `/api/projects/${encodeURIComponent(projectId)}/resources/${encodeURIComponent(resourceId)}/file?representation=${representation}`;
}

export function useDraft<T extends Record<string, unknown>>(project: Project, scope: string, initial: T, mutate: Mutate) {
  const key = `video-anatomy:1.8:${project.id}:${scope}`;
  const initialServer = (project.editor_drafts[scope] as T | undefined) ?? initial;
  const initialVersion = project.editor_draft_versions?.[scope] ?? 0;
  const [seed] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw) {
        const stored = JSON.parse(raw) as { content?: T; base_version?: number };
        if (stored.content && typeof stored.base_version === 'number') {
          const different = JSON.stringify(stored.content) !== JSON.stringify(initialServer);
          return { content: stored.content, version: stored.base_version, dirty: different, conflict: different && stored.base_version !== initialVersion };
        }
      }
    } catch { /* Server draft remains available. */ }
    return { content: initialServer, version: initialVersion, dirty: false, conflict: false };
  });
  const [draft, setDraft] = useState<T>(seed.content);
  const [conflict, setConflict] = useState(seed.conflict);
  const latest = useRef(seed.content);
  const baseVersion = useRef(seed.version);
  const dirty = useRef(seed.dirty);
  const conflicted = useRef(seed.conflict);
  const server = useRef({ content: initialServer, version: initialVersion });
  const saveQueue = useRef<Promise<boolean>>(Promise.resolve(true));
  const retain = useCallback((content: T, version: number) => {
    try { localStorage.setItem(key, JSON.stringify({ content, base_version: version })); } catch { /* Project saving remains available. */ }
  }, [key]);
  const reportConflict = useCallback(() => {
    conflicted.current = true; setConflict(true);
    window.dispatchEvent(new CustomEvent('va-draft-conflict', { detail: scope }));
  }, [scope]);
  const serverVersion = project.editor_draft_versions?.[scope] ?? 0;
  const serverContent = project.editor_drafts[scope] as T | undefined;
  useEffect(() => {
    const content = serverContent ?? initialServer;
    server.current = { content, version: serverVersion };
    if (serverVersion === baseVersion.current) return;
    if (dirty.current && JSON.stringify(latest.current) !== JSON.stringify(content)) { reportConflict(); return; }
    baseVersion.current = serverVersion; latest.current = content; dirty.current = false;
    conflicted.current = false; setConflict(false); setDraft(content); retain(content, serverVersion);
  }, [serverVersion, serverContent, initialServer, reportConflict, retain]);
  const flush = useCallback((): Promise<boolean> => {
    const operation = saveQueue.current.then(async () => {
      if (conflicted.current) { reportConflict(); return false; }
      if (!dirty.current) return true;
      const submitted = latest.current;
      const saved = await mutate('', { editor_drafts: { [scope]: submitted }, expected_editor_versions: { [scope]: baseVersion.current } }, 'PATCH');
      if (!saved) return false;
      const version = saved.editor_draft_versions?.[scope] ?? 0;
      baseVersion.current = version;
      if (latest.current === submitted) dirty.current = false;
      retain(latest.current, version);
      return true;
    });
    saveQueue.current = operation;
    return operation;
  }, [mutate, scope, retain, reportConflict]);
  const update = useCallback((value: T) => {
    latest.current = value; dirty.current = true; setDraft(value); retain(value, baseVersion.current);
  }, [retain]);
  const reload = useCallback(() => {
    latest.current = server.current.content; baseVersion.current = server.current.version;
    dirty.current = false; conflicted.current = false; setConflict(false); setDraft(server.current.content);
    retain(server.current.content, server.current.version);
  }, [retain]);
  useEffect(() => {
    if (!dirty.current || conflict) return;
    const timer = window.setTimeout(() => { void flush(); }, 650);
    return () => window.clearTimeout(timer);
  }, [draft, conflict, flush]);
  useEffect(() => () => { void flush(); }, [flush]);
  useEffect(() => {
    const scopes = draftFlushers.get(project.id) ?? new Map<string, () => Promise<boolean>>();
    const settle = async () => {
      for (let attempt = 0; attempt < 4; attempt += 1) {
        if (!await flush()) return false;
        if (!dirty.current) return true;
      }
      return false;
    };
    scopes.set(scope, settle); draftFlushers.set(project.id, scopes);
    return () => { if (scopes.get(scope) === settle) scopes.delete(scope); if (!scopes.size) draftFlushers.delete(project.id); };
  }, [project.id, scope, flush]);
  const acknowledgedVersion = useCallback(() => baseVersion.current, []);
  const adoptSaved = useCallback((saved: Project, fallback: T) => {
    const content = (saved.editor_drafts[scope] as T | undefined) ?? fallback;
    const version = saved.editor_draft_versions?.[scope] ?? baseVersion.current;
    latest.current = content; baseVersion.current = version; dirty.current = false;
    server.current = { content, version }; conflicted.current = false;
    setConflict(false); setDraft(content); retain(content, version);
  }, [scope, retain]);
  return [draft, update, flush, conflict, reload, acknowledgedVersion, adoptSaved] as const;
}
