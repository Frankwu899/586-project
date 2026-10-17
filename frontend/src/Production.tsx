import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { ProductionCreativeBrief, TaskState, StoryboardRow } from './generated/contracts';
import { Badge, Field, seconds, type Mutate } from './ui';
import { useEditorDraft } from './useEditorDraft';
import { currentProduction, evidenceDescription, productionFilename, productionHtml, productionMarkdown, productionStatus, sourceSummary, storyboardCsv, type ProductionSnapshot } from './productionExports';
import './production.css';

type ExportFormat = 'pdf' | 'csv' | 'markdown';
type ProductionContent = {
  brief_fields: Pick<ProductionCreativeBrief, 'title' | 'core_message' | 'hook' | 'narrative' | 'cta' | 'production_notes'>;
  rows: StoryboardRow[];
};
type PendingAction = { kind: 'export'; format: ExportFormat } | { kind: 'regenerate' } | { kind: 'discard' };

function SaveDialog({ title, children, onClose }: { title: string; children: ReactNode; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog className="production-dialog" ref={dialog} onCancel={onClose} aria-labelledby="production-dialog-title"><h3 id="production-dialog-title">{title}</h3>{children}</dialog>;
}

function PdfPreview({ snapshot, onClose }: { snapshot: ProductionSnapshot; onClose: () => void }) {
  const frame = useRef<HTMLIFrameElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} className="production-preview" aria-labelledby="production-preview-title" onCancel={onClose}>
    <div className="production-preview-toolbar"><div><h3 id="production-preview-title">Production document preview</h3><p>Choose “Save as PDF” in your browser’s print dialog. This preview uses the saved version below.</p></div><div className="actions"><button disabled={!ready} type="button" onClick={() => { frame.current?.contentWindow?.focus(); frame.current?.contentWindow?.print(); }}>Print / Save as PDF</button><button className="secondary" type="button" onClick={onClose}>Close preview</button></div></div>
    <iframe ref={frame} title="Saved production document" srcDoc={productionHtml(snapshot)} onLoad={() => setReady(true)} />
  </dialog>;
}

function download(snapshot: ProductionSnapshot, format: Exclude<ExportFormat, 'pdf'>) {
  const blob = new Blob([format === 'csv' ? storyboardCsv(snapshot) : productionMarkdown(snapshot)], { type: format === 'csv' ? 'text/csv;charset=utf-8' : 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = productionFilename(snapshot, format === 'csv' ? 'csv' : 'md');
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function SavedHistory({ state, onExport, busy }: { state: TaskState; onExport: (snapshot: ProductionSnapshot, format: ExportFormat) => void; busy: boolean }) {
  const oldBriefs = state.production_briefs.filter((item) => item.output_id !== state.task.current_production_brief?.id || item.revision !== state.task.current_production_brief.revision);
  const oldStories = state.storyboards.filter((item) => item.output_id !== state.task.current_storyboard?.id || item.revision !== state.task.current_storyboard.revision);
  if (!oldBriefs.length && !oldStories.length) return null;
  return <details className="production-history"><summary>Earlier saved production versions ({oldBriefs.length + oldStories.length})</summary><p className="muted">Each historical artifact retains its exact sources. Exported files are clearly marked as historical.</p>
    {[...oldBriefs].reverse().map((brief) => <article key={`${brief.output_id}:${brief.revision}`}><div><h4>{brief.title}</h4><p>Production brief · revision {brief.revision} · {brief.edited ? 'manually edited' : 'generated'}</p></div><div className="actions"><button className="secondary" disabled={busy} type="button" onClick={() => onExport({ state, brief, storyboard: null, historical: true }, 'pdf')}>Historical brief PDF · r{brief.revision}</button><button className="text-button" disabled={busy} type="button" onClick={() => onExport({ state, brief, storyboard: null, historical: true }, 'markdown')}>Markdown</button></div></article>)}
    {[...oldStories].reverse().map((storyboard) => <article key={`${storyboard.output_id}:${storyboard.revision}`}><div><h4>Text storyboard</h4><p>Revision {storyboard.revision} · {storyboard.rows.length} shots · {seconds(storyboard.target_duration_seconds)}</p></div><div className="actions"><button className="secondary" disabled={busy} type="button" onClick={() => onExport({ state, brief: null, storyboard, historical: true }, 'pdf')}>Historical storyboard PDF · r{storyboard.revision}</button><button className="secondary" disabled={busy} type="button" onClick={() => onExport({ state, brief: null, storyboard, historical: true }, 'csv')}>Historical CSV · r{storyboard.revision}</button></div></article>)}
  </details>;
}

function OutputEditor({ state, snapshot, mutate, busy, canGenerate, onExport }: { state: TaskState; snapshot: ProductionSnapshot; mutate: Mutate; busy: boolean; canGenerate: boolean; onExport: (snapshot: ProductionSnapshot, format: ExportFormat) => void }) {
  const brief = snapshot.brief!;
  const storyboard = snapshot.storyboard!;
  const draft = useEditorDraft<ProductionContent>({ taskId: state.task.task_id, scope: 'production', baseRefs: { production_brief: { id: brief.output_id, revision: brief.revision }, storyboard: { id: storyboard.output_id, revision: storyboard.revision } }, initialContent: { brief_fields: { title: brief.title, core_message: brief.core_message, hook: brief.hook, narrative: brief.narrative, cta: brief.cta, production_notes: brief.production_notes }, rows: storyboard.rows } });
  const [action, setAction] = useState<PendingAction | null>(null);
  const [localError, setLocalError] = useState('');
  const [localNotice, setLocalNotice] = useState('');
  const [working, setWorking] = useState(false);
  const form = useRef<HTMLFormElement>(null);
  const { reload } = draft;
  useEffect(() => { void reload().catch((failure: unknown) => setLocalError(failure instanceof Error ? failure.message : 'Could not refresh the saved production draft.')); }, [brief.output_id, brief.revision, storyboard.output_id, storyboard.revision, reload]);
  const fields = draft.content.brief_fields;
  const rows = draft.content.rows;
  const sourceAnalysis = state.analyses.find((item) => item.analysis_id === brief.analysis_ref.id && item.revision === brief.analysis_ref.revision);
  const sourceDeleted = state.videos.some((item) => item.video_id === sourceAnalysis?.video_id && item.deleted_at);
  const unavailable = busy || working || draft.loading;
  const setField = (field: keyof ProductionContent['brief_fields'], value: string | string[]) => draft.setContent((previous) => ({ ...previous, brief_fields: { ...previous.brief_fields, [field]: value } }));
  const setRow = (id: string, field: 'visual' | 'dialogue' | 'on_screen_text' | 'sound' | 'cta', value: string) => draft.setContent((previous) => ({ ...previous, rows: previous.rows.map((row) => row.row_id === id ? { ...row, [field]: value } : row) }));
  const save = async (): Promise<TaskState | false> => {
    if (draft.conflict) { setLocalError('This draft belongs to an earlier production version. Keep a copy of your changes, then explicitly discard the draft to load the latest saved version.'); return false; }
    if (!form.current?.reportValidity()) return false;
    const flushed = await draft.flush();
    if (!flushed.has_pending_changes) return state;
    const result = await mutate('/outputs/edit', { production_brief_ref: flushed.base_refs.production_brief, storyboard_ref: flushed.base_refs.storyboard, expected_editor_version: flushed.draft_version, ...flushed.content });
    if (!result) { setLocalError('Production changes could not be saved. Your draft is retained. Nothing was exported.'); return false; }
    await draft.reload();
    return result;
  };
  const regenerate = async () => {
    const result = await mutate('/outputs/generate', { direction_ref: state.task.selected_direction, brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis });
    if (result) await draft.reload();
  };
  const run = async (operation: () => Promise<void>) => {
    setWorking(true); setLocalError(''); setLocalNotice('');
    try { await operation(); } catch (failure) { setLocalError(failure instanceof Error ? failure.message : 'The operation failed. Your changes remain available.'); }
    finally { setWorking(false); }
  };
  const requestExport = (format: ExportFormat) => {
    if (draft.pending || draft.conflict) setAction({ kind: 'export', format });
    else { const saved = currentProduction(state); if (saved) onExport(saved, format); }
  };
  const resolveAction = (discard: boolean) => run(async () => {
    if (!action) return;
    if (discard) { await draft.discard(); if (action.kind === 'discard') { setAction(null); return; } }
    else {
      const saved = await save();
      if (!saved) { setAction(null); return; }
      if (action.kind === 'export') { const savedSnapshot = currentProduction(saved); if (savedSnapshot) onExport(savedSnapshot, action.format); setAction(null); return; }
      // A formal save increments task.version. Let the next explicit generation
      // click use the newly rendered state instead of a stale mutation closure.
      if (action.kind === 'regenerate') { setAction(null); setLocalNotice('Changes saved. Click “Regenerate production materials” to create a new version from your approved direction.'); return; }
    }
    setAction(null);
    if (action.kind === 'regenerate') await regenerate();
  });
  return <>
    <div className="production-toolbar"><div><p className="production-eyebrow">Delivery draft</p><h3>{brief.title}</h3><p><Badge warning={brief.currentness !== 'current'}>{brief.currentness === 'current' ? 'Saved version' : 'Historical version'}</Badge><Badge warning={brief.origin.kind === 'sample'}>{brief.origin.kind} output</Badge><span className="muted">Brief r{brief.revision} · Storyboard r{storyboard.revision}</span></p></div><button type="button" className="secondary" disabled={unavailable || !canGenerate} onClick={() => { if (draft.pending || draft.conflict) setAction({ kind: 'regenerate' }); else void run(regenerate); }}>Regenerate production materials</button></div>
    {brief.currentness !== 'current' && <p className="notice">These materials are historical because their inputs or approved direction changed. Your saved work remains available. Approve a current direction before regenerating.</p>}
    {sourceDeleted && <p className="notice">Reference media deleted; playback unavailable. Saved observations and production history are retained.</p>}
    <div className="production-export-bar"><div><strong>Ready to share with your team</strong><p>PDF combines the brief and storyboard. CSV keeps shot text editable in a spreadsheet.</p></div><div className="actions"><button disabled={unavailable} type="button" onClick={() => requestExport('pdf')}>{brief.currentness === 'current' ? 'Production PDF' : 'Export historical PDF'}</button><button disabled={unavailable} type="button" className="secondary" onClick={() => requestExport('csv')}>{storyboard.currentness === 'current' ? 'Storyboard CSV' : 'Export historical CSV'}</button><button disabled={unavailable} type="button" className="text-button" onClick={() => requestExport('markdown')}>Markdown</button></div></div>
    <details className="production-source"><summary>Source versions · inputs r{brief.brief_ref.revision} · analysis r{brief.analysis_ref.revision} · direction r{brief.direction_ref.revision}</summary><p className="muted">{sourceSummary(snapshot)}</p></details>
    <div className="production-save-status" role="status">{draft.loading ? 'Restoring production draft…' : draft.saving ? 'Saving draft…' : draft.conflict ? 'Draft conflict — your changes are retained' : draft.pending ? 'Pending draft changes · save to update the production version' : 'All production changes saved'}</div>
    {localNotice && <p className="success" role="status">{localNotice}</p>}
    {(localError || draft.error) && <p className="error" role="alert">{localError || draft.error}</p>}
    {draft.conflict && <p className="notice">The saved production version changed while this draft was open. Copy any text you need, then discard this draft to load the newer version. Nothing is overwritten automatically.</p>}
    <form ref={form} onSubmit={(event) => { event.preventDefault(); void run(async () => { await save(); }); }}>
      <fieldset disabled={unavailable}>
        <div className="production-section-heading"><span>01</span><div><h3>Production creative brief</h3><p>The idea, message and practical needs for the team making this video.</p></div></div>
        <div className="production-brief-grid"><Field label="Production title"><input required value={fields.title} onChange={(event) => setField('title', event.target.value)} /></Field><Field label="Production core message"><textarea required value={fields.core_message} onChange={(event) => setField('core_message', event.target.value)} /></Field><Field label="Production Hook"><textarea required value={fields.hook} onChange={(event) => setField('hook', event.target.value)} /></Field><Field label="Production narrative"><textarea required value={fields.narrative} onChange={(event) => setField('narrative', event.target.value)} /></Field><Field label="Production CTA"><textarea required value={fields.cta} onChange={(event) => setField('cta', event.target.value)} /></Field><Field label="Production notes" hint="Resources to prepare, production needs and restrictions. One note per line."><textarea value={fields.production_notes.join('\n')} onChange={(event) => setField('production_notes', event.target.value.split('\n'))} /></Field></div>
        <div className="production-section-heading"><span>02</span><div><h3>Text storyboard</h3><p>{rows.length} shots · {seconds(storyboard.target_duration_seconds)} planned video. Edit wording; generated shot order and timing stay fixed.</p></div></div>
        <div className="production-storyboard">{rows.map((row, index) => <article className="production-shot" key={row.row_id}>
          <div className="production-shot-index"><span>{String(index + 1).padStart(2, '0')}</span><strong>{seconds(row.start_seconds)}–{seconds(row.end_seconds)}</strong><small>Planned video</small></div>
          <div className="production-shot-content"><h4>Shot {index + 1}</h4><Badge warning={!row.evidence.length}>{row.evidence.length ? 'Reference-informed' : 'Original production suggestion'}</Badge><Field label={`Shot ${index + 1} visuals`}><textarea required value={row.visual} onChange={(event) => setRow(row.row_id, 'visual', event.target.value)} /></Field><div className="grid"><Field label={`Shot ${index + 1} dialogue`}><textarea value={row.dialogue ?? ''} onChange={(event) => setRow(row.row_id, 'dialogue', event.target.value)} /></Field><Field label={`Shot ${index + 1} on-screen text`}><textarea value={row.on_screen_text ?? ''} onChange={(event) => setRow(row.row_id, 'on_screen_text', event.target.value)} /></Field><Field label={`Shot ${index + 1} sound`}><textarea value={row.sound ?? ''} onChange={(event) => setRow(row.row_id, 'sound', event.target.value)} /></Field><Field label={`Shot ${index + 1} CTA`}><textarea value={row.cta ?? ''} onChange={(event) => setRow(row.row_id, 'cta', event.target.value)} /></Field></div>
          {row.evidence.length ? <details><summary>Reference connections ({row.evidence.length})</summary><ul className="production-evidence">{row.evidence.map((item, evidenceIndex) => <li key={evidenceIndex}>{evidenceDescription(state, item)}</li>)}</ul><p className="muted">Reference times describe the original video, independently of this shot’s planned timing.</p></details> : <p className="muted">A new production idea, without a reference citation. Use only confirmed product facts.</p>}</div>
        </article>)}</div>
        <div className="production-save-actions"><button type="submit" disabled={!draft.pending || draft.conflict}>Save production edits</button><button type="button" className="secondary" disabled={!draft.pending && !draft.conflict} onClick={() => setAction({ kind: 'discard' })}>Discard production draft</button><p>Drafts survive task switches. Saving creates a formal version; it does not call AI.</p></div>
      </fieldset>
    </form>
    {action && <SaveDialog title={action.kind === 'export' ? 'Save changes before exporting?' : action.kind === 'discard' ? 'Discard this production draft?' : 'Resolve your draft before regenerating'} onClose={() => setAction(null)}><p>{action.kind === 'export' ? 'Your latest text is still a draft. Save it successfully before exporting that exact version. No older version will be downloaded if saving fails.' : action.kind === 'discard' ? 'This removes the pending production changes and restores the saved version. Existing saved history stays available.' : 'Regeneration creates a new version. Save your current work to history, or discard the pending draft first.'}</p><div className="actions">{action.kind !== 'discard' && <button type="button" disabled={working || draft.conflict} onClick={() => void resolveAction(false)}>{action.kind === 'export' ? 'Save and export' : 'Save changes first'}</button>}{action.kind !== 'export' && <button type="button" className="secondary" disabled={working} onClick={() => void resolveAction(true)}>{action.kind === 'discard' ? 'Discard draft' : 'Discard draft and regenerate'}</button>}<button type="button" className="secondary" disabled={working} onClick={() => setAction(null)}>Cancel</button></div></SaveDialog>}
  </>;
}

export default function Production({ state, mutate, busy, m2Blocked }: { state: TaskState; mutate: Mutate; busy: boolean; m2Blocked: boolean }) {
  const current = currentProduction(state);
  const approved = state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision && item.approval_status === 'approved' && item.currentness === 'current');
  const [preview, setPreview] = useState<ProductionSnapshot | null>(null);
  const [historical, setHistorical] = useState<{ snapshot: ProductionSnapshot; format: ExportFormat } | null>(null);
  const performExport = (snapshot: ProductionSnapshot, format: ExportFormat) => { if (format === 'pdf') setPreview(snapshot); else download(snapshot, format); };
  const onExport = (snapshot: ProductionSnapshot, format: ExportFormat) => { if (snapshot.historical) setHistorical({ snapshot, format }); else performExport(snapshot, format); };
  return <section id="production" className="panel production-studio" aria-labelledby="production-heading">
    <div className="production-heading"><p className="production-eyebrow">04 / Make it tangible</p><h2 id="production-heading">Production & delivery</h2><p>Turn your approved idea into a brief and shot-by-shot plan the team can work with.</p></div>
    {!approved && <p className="notice">Explicitly approve a current direction to generate production materials. Existing work stays available below.</p>}
    {m2Blocked && <p className="notice">Resolve pending input or analysis changes before generating new production materials.</p>}
    {current?.brief && current.storyboard ? <OutputEditor key={state.task.task_id} state={state} snapshot={current} mutate={mutate} busy={busy} canGenerate={Boolean(approved) && !m2Blocked} onExport={onExport} /> : <div className="production-empty"><span>From an idea to a shoot.</span><p>Your production brief and timed storyboard will appear here after you approve a direction.</p><button type="button" disabled={busy || m2Blocked || !approved} onClick={() => mutate('/outputs/generate', { direction_ref: state.task.selected_direction, brief_ref: state.task.current_brief, analysis_ref: state.task.current_analysis })}>Generate production materials</button><p className="muted">Generated drafts remain editable. Earlier saved work is retained when you generate again.</p></div>}
    <SavedHistory state={state} onExport={onExport} busy={busy} />
    {historical && <SaveDialog title="Export a historical version?" onClose={() => setHistorical(null)}><p>{productionStatus(historical.snapshot)}. The filename and document will carry this label and the exact original source versions.</p><div className="actions"><button type="button" onClick={() => { performExport(historical.snapshot, historical.format); setHistorical(null); }}>Export historical version</button><button type="button" className="secondary" onClick={() => setHistorical(null)}>Cancel</button></div></SaveDialog>}
    {preview && <PdfPreview snapshot={preview} onClose={() => setPreview(null)} />}
  </section>;
}
