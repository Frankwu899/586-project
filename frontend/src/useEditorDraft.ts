import { useCallback, useEffect, useRef, useState, type SetStateAction } from 'react';
import { request } from './api';
import { EditorDraftSession, type EditorBaseRefs, type EditorDraft } from './editorDraftSession';

export type { EditorDraft, EditorBaseRefs } from './editorDraftSession';
export type EditorDraftStatus = { loading: boolean; saving: boolean; pending: boolean; conflict: boolean; error: string };
type RegisteredEditor = { taskId: string; flush: () => Promise<unknown>; pending: () => boolean };
const editors = new Map<symbol, RegisteredEditor>();

export async function flushEditorDrafts(taskId: string) {
  const current = [...editors.values()].filter((editor) => editor.taskId === taskId);
  await Promise.all(current.map((editor) => editor.flush()));
}
export function hasPendingEditorDrafts(taskId: string) {
  return [...editors.values()].some((editor) => editor.taskId === taskId && editor.pending());
}

type Recovery<T> = { draftVersion: number; baseRefs: EditorBaseRefs; content: T };
function readRecovery<T>(key: string): Recovery<T> | null {
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(key) ?? 'null');
    if (saved && typeof saved === 'object' && 'draftVersion' in saved && 'baseRefs' in saved && 'content' in saved) return saved as Recovery<T>;
  } catch { /* Browser storage may be unavailable. Server saves still work. */ }
  return null;
}

export function useEditorDraft<T>({ taskId, scope, baseRefs, initialContent }: {
  taskId: string; scope: string; baseRefs: EditorBaseRefs; initialContent: T;
}) {
  const base = `/tasks/${taskId}/editors/${scope}`;
  const recoveryKey = `video-anatomy-editor:${taskId}:${scope}`;
  const session = useRef<EditorDraftSession<T> | null>(null);
  const mounted = useRef(false);
  const [revision, render] = useState(0);
  const [loadError, setLoadError] = useState('');
  const initial = useRef(initialContent);
  const initialRefs = useRef(baseRefs);
  const notify = useCallback(() => {
    const current = session.current;
    if (current) {
      try {
        if (current.dirty) localStorage.setItem(recoveryKey, JSON.stringify({ draftVersion: current.current.draft_version, baseRefs: current.current.base_refs, content: current.current.content }));
        else localStorage.removeItem(recoveryKey);
      } catch { /* A save failure remains visible even if browser recovery storage is full. */ }
    }
    if (mounted.current) render((value) => value + 1);
  }, [recoveryKey]);

  useEffect(() => {
    mounted.current = true;
    let cancelled = false;
    const token = Symbol(scope);
    const load = request<EditorDraft<T>>(base).then((saved) => {
      if (cancelled || session.current) return;
      const fallback = readRecovery<T>(recoveryKey);
      const channel = new EditorDraftSession<T>(saved, (input) => request<EditorDraft<T>>(base, input), notify);
      session.current = channel;
      if (fallback && JSON.stringify(fallback.content) !== JSON.stringify(saved.content)) {
        channel.recover(fallback.content, saved.draft_version !== fallback.draftVersion || JSON.stringify(saved.base_refs) !== JSON.stringify(fallback.baseRefs));
      }
      notify();
    }).catch((failure: unknown) => {
      if (!cancelled && !session.current) setLoadError(failure instanceof Error ? failure.message : 'Could not restore your saved draft.');
      throw failure;
    });
    void load.catch(() => undefined);
    // An editor still loading cannot have accepted new typing. Its failed read
    // must not trap the user in another area; the server still owns action gates.
    editors.set(token, { taskId, flush: async () => session.current?.flush(), pending: () => session.current?.pending ?? false });
    return () => { cancelled = true; mounted.current = false; editors.delete(token); };
  }, [base, notify, recoveryKey, scope, taskId]);

  useEffect(() => {
    const current = session.current;
    if (!current?.dirty || current.error || current.current.conflict) return;
    const timer = window.setTimeout(() => { void current.flush().catch(() => undefined); }, 450);
    return () => window.clearTimeout(timer);
  }, [revision]);

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (session.current?.dirty) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, []);

  const flush = useCallback(async () => {
    if (!session.current) throw new Error('Wait for your saved draft to load.');
    return session.current.flush();
  }, []);
  const reload = useCallback(async () => {
    const current = session.current;
    if (current?.dirty || current?.saving) return;
    const generation = current?.generation;
    const saved = await request<EditorDraft<T>>(base);
    setLoadError('');
    if (!current && mounted.current && !session.current) {
      const fallback = readRecovery<T>(recoveryKey);
      const channel = new EditorDraftSession<T>(saved, (input) => request<EditorDraft<T>>(base, input), notify);
      session.current = channel;
      if (fallback && JSON.stringify(fallback.content) !== JSON.stringify(saved.content)) channel.recover(fallback.content, saved.draft_version !== fallback.draftVersion || JSON.stringify(saved.base_refs) !== JSON.stringify(fallback.baseRefs));
      notify();
      return;
    }
    if (!current) return;
    if (session.current === current && !current.dirty && !current.saving && generation === current.generation) current.replace(saved);
  }, [base, notify, recoveryKey]);
  const referenceKey = JSON.stringify(baseRefs);
  const previousReferenceKey = useRef(referenceKey);
  useEffect(() => {
    if (previousReferenceKey.current === referenceKey) return;
    previousReferenceKey.current = referenceKey;
    void reload().catch((failure: unknown) => setLoadError(failure instanceof Error ? failure.message : 'Could not refresh this draft. Your text is retained.'));
  }, [referenceKey, reload]);
  const discard = useCallback(async () => {
    const current = session.current;
    if (!current) throw new Error('Wait for your saved draft to load.');
    if (current.saving) await current.flush().catch(() => undefined);
    // A browser-recovered conflict must not discard another tab's newer server draft.
    if (current.current.conflict && current.dirty) {
      const saved = await request<EditorDraft<T>>(base);
      current.replace(saved);
      return;
    }
    const saved = await request<EditorDraft<T>>(`${base}/discard`, { expected_draft_version: current.current.draft_version });
    current.replace(saved);
  }, [base]);
  const setContent = useCallback((value: SetStateAction<T>) => {
    const current = session.current;
    if (!current) return;
    current.edit(typeof value === 'function' ? (value as (previous: T) => T)(current.current.content) : value);
  }, []);

  const current = session.current;
  return {
    content: current?.current.content ?? initial.current,
    baseRefs: current?.current.base_refs ?? initialRefs.current,
    setContent,
    loading: !current,
    saving: current?.saving ?? false,
    pending: current?.pending ?? false,
    conflict: current?.current.conflict ?? false,
    error: loadError || current?.error || '',
    expectedVersion: current?.current.draft_version ?? null,
    flush, discard, reload,
  };
}
