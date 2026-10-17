import type { M2Draft, M2DraftUpdate } from './generated/contracts';

/** One serialized editor channel. Task mutations and provider jobs never enter it. */
export class M2DraftSession {
  current: M2Draft;
  error = '';
  saving = false;
  private sequence = 0;
  private acknowledged = 0;
  private operation: Promise<M2Draft> | null = null;
  private savedStructured: string;

  constructor(initial: M2Draft, private persist: (input: M2DraftUpdate) => Promise<M2Draft>, private notify: () => void) {
    this.current = initial;
    this.savedStructured = this.structured(initial);
  }

  private structured(draft: M2Draft) { return JSON.stringify([draft.fields, draft.claims]); }
  get dirty() { return this.sequence !== this.acknowledged; }
  get generation() { return this.sequence; }
  get pending() { return this.current.has_pending_inputs || this.structured(this.current) !== this.savedStructured; }

  edit(update: (draft: M2Draft) => M2Draft) {
    this.current = update(this.current);
    this.error = '';
    this.sequence += 1;
    this.notify();
  }

  replace(saved: M2Draft) {
    if (this.saving) throw new Error('Wait for the draft save to finish.');
    this.current = saved;
    this.sequence += 1;
    this.acknowledged = this.sequence;
    this.savedStructured = this.structured(saved);
    this.error = '';
    this.notify();
  }

  flush(): Promise<M2Draft> {
    if (this.operation) return this.operation;
    if (!this.dirty) return Promise.resolve(this.current);
    this.saving = true;
    this.error = '';
    this.notify();
    this.operation = (async () => {
      try {
        while (this.dirty) {
          const sent = this.current;
          const sentSequence = this.sequence;
          const saved = await this.persist({ expected_draft_version: sent.draft_version, fields: sent.fields, claims: sent.claims, source_notes: sent.source_notes });
          this.acknowledged = sentSequence;
          this.savedStructured = this.structured(saved);
          // A delayed acknowledgement updates version metadata, never newer local text.
          this.current = sentSequence === this.sequence ? saved : { ...saved, fields: this.current.fields, claims: this.current.claims, source_notes: this.current.source_notes };
          this.notify();
        }
        return this.current;
      } catch (failure) {
        this.error = failure instanceof Error ? failure.message : 'Could not save your draft.';
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
