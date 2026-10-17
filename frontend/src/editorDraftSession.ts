export type EditorBaseRefs = Record<string, { id: string; revision: number }>;
export interface EditorDraft<T = Record<string, unknown>> {
  task_id: string;
  scope: string;
  draft_version: number;
  base_refs: EditorBaseRefs;
  content: T;
  has_pending_changes: boolean;
  conflict: boolean;
  updated_at: string;
}
export interface EditorDraftUpdate<T> {
  expected_draft_version: number;
  base_refs: EditorBaseRefs;
  content: T;
}

/** Independent serialized saves: an acknowledgement must never replace newer typing. */
export class EditorDraftSession<T> {
  current: EditorDraft<T>;
  error = '';
  saving = false;
  private sequence = 0;
  private acknowledged = 0;
  private operation: Promise<EditorDraft<T>> | null = null;
  private savedContent: string;

  constructor(initial: EditorDraft<T>, private persist: (input: EditorDraftUpdate<T>) => Promise<EditorDraft<T>>, private notify: () => void) {
    this.current = initial;
    this.savedContent = JSON.stringify(initial.content);
  }

  get dirty() { return this.sequence !== this.acknowledged; }
  get pending() { return this.current.has_pending_changes || JSON.stringify(this.current.content) !== this.savedContent; }
  get generation() { return this.sequence; }

  edit(content: T) {
    if (JSON.stringify(content) === JSON.stringify(this.current.content)) return;
    this.current = { ...this.current, content };
    this.sequence += 1;
    this.error = '';
    this.notify();
  }

  recover(content: T, conflict: boolean) {
    this.edit(content);
    if (conflict) {
      this.current = { ...this.current, conflict: true };
      this.error = 'A newer saved draft exists. Your recovered text is retained. Copy it before discarding the recovered draft to load the saved version.';
    }
    this.notify();
  }

  replace(saved: EditorDraft<T>) {
    if (this.saving) throw new Error('Wait for the draft save to finish.');
    this.current = saved;
    this.sequence += 1;
    this.acknowledged = this.sequence;
    this.savedContent = JSON.stringify(saved.content);
    this.error = '';
    this.notify();
  }

  flush(): Promise<EditorDraft<T>> {
    if (this.operation) return this.operation;
    if (!this.dirty) return Promise.resolve(this.current);
    if (this.current.conflict) return Promise.reject(new Error(this.error || 'This draft is based on an older version. Preserve your text and resolve the conflict before continuing.'));
    this.saving = true;
    this.error = '';
    this.notify();
    this.operation = (async () => {
      try {
        while (this.dirty) {
          const sent = this.current;
          const sentSequence = this.sequence;
          const saved = await this.persist({ expected_draft_version: sent.draft_version, base_refs: sent.base_refs, content: sent.content });
          this.acknowledged = sentSequence;
          this.savedContent = JSON.stringify(saved.content);
          this.current = sentSequence === this.sequence ? saved : { ...saved, content: this.current.content };
          this.notify();
        }
        return this.current;
      } catch (failure) {
        this.error = failure instanceof Error ? failure.message : 'Could not save your draft. Your text is retained.';
        if (failure && typeof failure === 'object' && 'status' in failure && failure.status === 409) {
          this.current = { ...this.current, conflict: true };
          this.error = `${this.error} Your text is retained. Copy any changes you need, then discard the recovered draft to load the newer saved version.`;
        }
        this.notify();
        throw failure;
      } finally {
        this.saving = false;
        this.operation = null;
        this.notify();
      }
    })();
    return this.operation;
  }
}
