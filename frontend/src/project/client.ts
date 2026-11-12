import { useCallback, useEffect, useRef, useState } from 'react';
import type { Project } from './contracts';

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
    throw new ProjectError(typeof error === 'string' ? error : error?.message ?? 'The operation could not be completed.', response.status, error?.code);
  }
  return data as T;
}

export type Mutate = (path: string, body?: Record<string, unknown> | FormData, method?: string) => Promise<Project | null>;
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
    try { accept(await call<Project>(`/${id}`)); if (!saved) setError('Some edits could not be saved to the project. Their local drafts are retained for recovery.'); }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not open project.'); }
  }, [accept]);
  const close = useCallback(async () => {
    const saved = await flushProjectDrafts(current.current?.id);
    await queue.current;
    current.current = null; setProject(null); void refreshList();
    if (!saved) setError('Some edits could not be saved to the project. Their local drafts are retained; reopen the project to review them.');
  }, [refreshList]);
  const mutate = useCallback<Mutate>((path, body = {}, method) => {
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
        setError(failure instanceof Error ? failure.message : 'Could not save. Your draft is retained.');
        if (failure instanceof ProjectError && failure.status === 409) {
          try {
            const fresh = await call<Project>(`/${projectId}`);
            if (current.current?.id === projectId) accept(fresh);
            const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
            let safe = false;
            if (baseline && !(body instanceof FormData)) {
              if (method === 'PATCH' && !body.expected_editor_versions) safe = Object.keys(body).every(key => key === 'editor_drafts'
                ? Object.keys(body.editor_drafts as Record<string, unknown>).every(scope => same(baseline!.editor_drafts[scope], fresh.editor_drafts[scope]))
                : same(baseline![key as keyof Project], fresh[key as keyof Project]));
              if (path === '/brief/draft' && !/draft.*conflict/.test(failure.code ?? '')) safe = same(baseline.brief_draft, fresh.brief_draft);
            }
            if (safe && !(payload instanceof FormData)) {
              const retried = await call<Project>(`/${projectId}${path}`, { ...payload, expected_version: fresh.version }, method);
              if (current.current?.id === projectId) accept(retried);
              setError(''); return retried;
            }
            setError('This project changed while saving. Your draft is retained. Review the latest saved content before applying it.');
          } catch { /* Retain current state and draft. */ }
        }
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
