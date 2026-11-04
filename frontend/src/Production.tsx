import { useI18n } from './i18n';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import type { ProductionCreativeBrief, TaskState, StoryboardRow } from './generated/contracts';
import { Badge, Field, seconds, type Mutate } from './ui';
import { useEditorDraft } from './useEditorDraft';
import { ConnectionHelp } from './ApiConnection';
import type { M2EditorStatus } from './BriefEditor';
import { productionBlocker, type ProductionBlocker, type ProductionDestination } from './productionReadiness';
import { currentProduction, productionFilename, productionHtml, productionMarkdown, productionStatus, sourceSummary, storyboardCsv, type ProductionSnapshot } from './productionExports';
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
  const { t } = useI18n();
  const frame = useRef<HTMLIFrameElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => { const element = dialog.current; element?.showModal(); return () => element?.close(); }, []);
  return <dialog ref={dialog} className="production-preview" aria-labelledby="production-preview-title" onCancel={onClose}>
    <div className="production-preview-toolbar"><div><h3 id="production-preview-title">{t("Production document preview")}</h3><p>{t("Choose “Save as PDF” in your browser’s print dialog. This preview uses the saved version below.")}</p></div><div className="actions"><button disabled={!ready} type="button" onClick={() => { frame.current?.contentWindow?.focus(); frame.current?.contentWindow?.print(); }}>{t("Print / Save as PDF")}</button><button className="secondary" type="button" onClick={onClose}>{t("Close preview")}</button></div></div>
    <iframe ref={frame} title={t("Saved production document")} srcDoc={productionHtml(snapshot)} onLoad={() => setReady(true)} />
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
  const { t } = useI18n();
  const oldBriefs = state.production_briefs.filter((item) => item.output_id !== state.task.current_production_brief?.id || item.revision !== state.task.current_production_brief.revision);
  const oldStories = state.storyboards.filter((item) => item.output_id !== state.task.current_storyboard?.id || item.revision !== state.task.current_storyboard.revision);
  if (!oldBriefs.length && !oldStories.length) return null;
  return <div className="production-history"><h4>{t("Earlier versions")}</h4>
    {[...oldBriefs].reverse().map((brief) => <article key={`${brief.output_id}:${brief.revision}`}><div><h4>{brief.title}</h4><p>{t("Production brief · revision")} {brief.revision} · {brief.edited ? t("manually edited") : t("generated")}</p></div><div className="actions"><button className="secondary" disabled={busy} type="button" onClick={() => onExport({ state, brief, storyboard: null, historical: true }, 'pdf')}>{t("Historical brief PDF · r")}{brief.revision}</button><button className="text-button" disabled={busy} type="button" onClick={() => onExport({ state, brief, storyboard: null, historical: true }, 'markdown')}>{t("Markdown")}</button></div></article>)}
    {[...oldStories].reverse().map((storyboard) => <article key={`${storyboard.output_id}:${storyboard.revision}`}><div><h4>{t("Text storyboard")}</h4><p>{t("Revision")} {storyboard.revision} · {storyboard.rows.length}  {t("shots ·")} {seconds(storyboard.target_duration_seconds)}</p></div><div className="actions"><button className="secondary" disabled={busy} type="button" onClick={() => onExport({ state, brief: null, storyboard, historical: true }, 'pdf')}>{t("Historical storyboard PDF · r")}{storyboard.revision}</button><button className="secondary" disabled={busy} type="button" onClick={() => onExport({ state, brief: null, storyboard, historical: true }, 'csv')}>{t("Historical CSV · r")}{storyboard.revision}</button></div></article>)}
  </div>;
}

function GenerationBlocker({ blocker, onNavigate }: { blocker: ProductionBlocker | null; onNavigate: (target: ProductionDestination) => void }) {
  const { t } = useI18n();
  if (!blocker) return null;
  return <div className="production-prerequisite" role="status"><span>{t(blocker.message)}</span>{blocker.destination && blocker.action && <button className="text-button" type="button" onClick={() => onNavigate(blocker.destination!)}>{t(blocker.action)}</button>}</div>;
}

function ExportMenu({ historical, disabled, onExport }: { historical: boolean; disabled: boolean; onExport: (format: ExportFormat) => void }) {
  const { t } = useI18n();
  const menu = useRef<HTMLDetailsElement>(null);
  const choose = (format: ExportFormat) => { if (menu.current) menu.current.open = false; onExport(format); };
  return <details ref={menu} className="production-export-bar" onKeyDown={(event) => { if (event.key === 'Escape' && menu.current?.open) { event.preventDefault(); menu.current.open = false; menu.current.querySelector('summary')?.focus(); } }}>
    <summary>{t("Export")}</summary><div className="production-export-options"><button disabled={disabled} type="button" onClick={() => choose('pdf')}>{historical ? t("Export historical PDF") : t("Production PDF")}</button><button disabled={disabled} type="button" onClick={() => choose('csv')}>{historical ? t("Export historical CSV") : t("Storyboard CSV")}</button><button disabled={disabled} type="button" onClick={() => choose('markdown')}>{t("Markdown")}</button></div>
  </details>;
}

function OutputEditor({ state, snapshot, mutate, busy, actionError, blocker, onNavigate, historyControl, onExport }: { state: TaskState; snapshot: ProductionSnapshot; mutate: Mutate; busy: boolean; actionError?: string; blocker: ProductionBlocker | null; onNavigate: (target: ProductionDestination) => void; historyControl: ReactNode; onExport: (snapshot: ProductionSnapshot, format: ExportFormat) => void }) {
  const { t } = useI18n();
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
  const sourceAnalysis = state.analyses.find((item) => item.analysis_id === brief.analysis_ref?.id && item.revision === brief.analysis_ref?.revision);
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
    const result = await mutate('/outputs/generate', { direction_ref: state.task.selected_direction, brief_ref: state.task.current_brief, analysis_ref: state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision)?.analysis_ref ?? null });
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
    <div className="production-toolbar"><div><h2 id="production-heading">{brief.title}</h2><div className="production-labels">{snapshot.historical && <Badge warning>{t("Historical version")}</Badge>}{brief.origin.kind === 'sample' && <Badge>{t("Fictional sample")}</Badge>}</div></div><div className="actions">
      <button type="button" className="secondary" disabled={unavailable || Boolean(blocker)} onClick={() => { if (draft.pending || draft.conflict) setAction({ kind: 'regenerate' }); else void run(regenerate); }}>{t("Regenerate production materials")}</button>
      <ExportMenu historical={snapshot.historical} disabled={unavailable} onExport={requestExport} />{historyControl}
    </div></div>
    {!busy && <GenerationBlocker blocker={blocker} onNavigate={onNavigate} />}
    {sourceDeleted && <p className="production-source-status">{t("Reference media deleted; playback unavailable.")}</p>}
    {(draft.loading || draft.saving || draft.pending || draft.conflict) && <div className="production-save-status" role="status">{draft.loading ? t("Restoring production draft…") : draft.saving ? t("Saving draft…") : draft.conflict ? t("Draft conflict — your changes are retained") : t("Draft changes need to be applied.")}</div>}
    {(draft.pending || draft.conflict) && <div className="production-save-actions"><button type="submit" form="production-edit-form" disabled={unavailable || !draft.pending || draft.conflict}>{t("Save production edits")}</button><button type="button" className="secondary" disabled={unavailable} onClick={() => setAction({ kind: 'discard' })}>{t("Discard production draft")}</button></div>}
    {localNotice && <p className="success" role="status">{t(localNotice)}</p>}
    {(localError || draft.error || actionError) && <div className="error" role="alert">{t(localError || draft.error || actionError || '')}<ConnectionHelp message={localError || draft.error || actionError} /></div>}
    {draft.conflict && <p className="notice">{t("The saved production version changed while this draft was open. Copy any text you need, then discard this draft to load the newer version. Nothing is overwritten automatically.")}</p>}
    <form id="production-edit-form" ref={form} onSubmit={(event) => { event.preventDefault(); void run(async () => { await save(); }); }}>
      <fieldset disabled={unavailable}>
        <div className="production-section-heading"><h3>{t("Production creative brief")}</h3></div>
        <div className="production-brief-grid"><Field label={t("Production title")}><input required value={fields.title} onChange={(event) => setField('title', event.target.value)} /></Field><Field label={t("Production core message")}><textarea required value={fields.core_message} onChange={(event) => setField('core_message', event.target.value)} /></Field><Field label={t("Production Hook")}><textarea required value={fields.hook} onChange={(event) => setField('hook', event.target.value)} /></Field><Field label={t("Production narrative")}><textarea required value={fields.narrative} onChange={(event) => setField('narrative', event.target.value)} /></Field><Field label={t("Production CTA")}><textarea required value={fields.cta} onChange={(event) => setField('cta', event.target.value)} /></Field><Field label={t("Production notes")} hint={t("Resources to prepare, production needs and restrictions. One note per line.")}><textarea value={fields.production_notes.join('\n')} onChange={(event) => setField('production_notes', event.target.value.split('\n'))} /></Field></div>
        <div className="production-section-heading"><h3>{t("Text storyboard")}</h3><p>{rows.length} {t("shots ·")} {seconds(storyboard.target_duration_seconds)}</p></div>
        <div className="production-storyboard">{rows.map((row, index) => <article className="production-shot" key={row.row_id}>
          <div className="production-shot-index"><span>{String(index + 1).padStart(2, '0')}</span><strong>{seconds(row.start_seconds)}–{seconds(row.end_seconds)}</strong></div>
          <div className="production-shot-content"><h4>{t("Shot")} {index + 1}</h4><span className="production-shot-origin">{row.evidence.length ? t("Reference-informed") : t("Original production suggestion")}</span><Field label={t("Shot {index} visuals", { index: index + 1 })}><textarea required value={row.visual} onChange={(event) => setRow(row.row_id, 'visual', event.target.value)} /></Field><div className="grid"><Field label={t("Shot {index} dialogue", { index: index + 1 })}><textarea value={row.dialogue ?? ''} onChange={(event) => setRow(row.row_id, 'dialogue', event.target.value)} /></Field><Field label={t("Shot {index} on-screen text", { index: index + 1 })}><textarea value={row.on_screen_text ?? ''} onChange={(event) => setRow(row.row_id, 'on_screen_text', event.target.value)} /></Field><Field label={t("Shot {index} sound", { index: index + 1 })}><textarea value={row.sound ?? ''} onChange={(event) => setRow(row.row_id, 'sound', event.target.value)} /></Field><Field label={t("Shot {index} CTA", { index: index + 1 })}><textarea value={row.cta ?? ''} onChange={(event) => setRow(row.row_id, 'cta', event.target.value)} /></Field></div>
          {row.evidence.length ? <details><summary>{t("Reference connections (")}{row.evidence.length})</summary><ul className="production-evidence">{row.evidence.map((item, evidenceIndex) => <li key={evidenceIndex}>{(() => {
            const analysis = state.analyses.find((entry) => entry.analysis_id === item.analysis_id && entry.revision === item.analysis_revision);
            const event = analysis?.events.find((entry) => entry.event_id === item.event_id);
            const video = state.videos.find((entry) => entry.video_id === item.video_id);
            const boundaries = video?.frame_timing?.frame_boundaries_seconds;
            const start = event?.start_frame == null ? undefined : boundaries?.[event.start_frame];
            const end = event?.end_frame == null ? undefined : boundaries?.[event.end_frame];
            return <>{start !== undefined && end !== undefined && <span className="production-evidence-time">{seconds(start)}–{seconds(end)} · </span>}{event?.text || event?.description || t("Evidence unavailable")}<p>{item.reason}</p></>;
          })()}</li>)}</ul></details> : null}</div>
        </article>)}</div>
      </fieldset>
    </form>
    {action && <SaveDialog title={action.kind === 'export' ? t("Save changes before exporting?") : action.kind === 'discard' ? t("Discard this production draft?") : t("Resolve your draft before regenerating")} onClose={() => setAction(null)}><p>{action.kind === 'export' ? t("Your latest text is still a draft. Save it successfully before exporting that exact version. No older version will be downloaded if saving fails.") : action.kind === 'discard' ? t("This removes the pending production changes and restores the saved version. Existing saved history stays available.") : t("Regeneration creates a new version. Save your current work to history, or discard the pending draft first.")}</p><div className="actions">{action.kind !== 'discard' && <button type="button" disabled={working || draft.conflict} onClick={() => void resolveAction(false)}>{action.kind === 'export' ? t("Save and export") : t("Save changes first")}</button>}{action.kind !== 'export' && <button type="button" className="secondary" disabled={working} onClick={() => void resolveAction(true)}>{action.kind === 'discard' ? t("Discard draft") : t("Discard draft and regenerate")}</button>}<button type="button" className="secondary" disabled={working} onClick={() => setAction(null)}>{t("Cancel")}</button></div></SaveDialog>}
  </>;
}

export default function Production({ state, mutate, busy, generating, actionError, contextStatus, analysisPending, directionPending, onNavigate }: { state: TaskState; mutate: Mutate; busy: boolean; generating: boolean; actionError?: string; contextStatus: M2EditorStatus; analysisPending: boolean; directionPending: boolean; onNavigate: (target: ProductionDestination) => void }) {
  const { t } = useI18n();
  const current = currentProduction(state);
  const blocker = productionBlocker(state, contextStatus, analysisPending, directionPending);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [preview, setPreview] = useState<ProductionSnapshot | null>(null);
  const [historical, setHistorical] = useState<{ snapshot: ProductionSnapshot; format: ExportFormat } | null>(null);
  const performExport = (snapshot: ProductionSnapshot, format: ExportFormat) => { if (format === 'pdf') setPreview(snapshot); else download(snapshot, format); };
  const onExport = (snapshot: ProductionSnapshot, format: ExportFormat) => { if (snapshot.historical) setHistorical({ snapshot, format }); else performExport(snapshot, format); };
  const historyControl = <button className="text-button" type="button" onClick={() => setHistoryOpen(true)}>{t("History")}</button>;
  return <section id="production" className="production-studio" aria-labelledby="production-heading">
    {generating && <p className="production-progress" role="status"><span className="spinner" aria-hidden="true" />{t("Generating production materials…")}</p>}
    {current?.brief && current.storyboard ? <OutputEditor key={state.task.task_id} state={state} snapshot={current} mutate={mutate} busy={busy} actionError={actionError} blocker={blocker} onNavigate={onNavigate} historyControl={historyControl} onExport={onExport} /> : <>
      <div className="production-toolbar"><h2 id="production-heading">{t("Production")}</h2><div className="actions"><button type="button" disabled={busy || Boolean(blocker)} onClick={() => mutate('/outputs/generate', { direction_ref: state.task.selected_direction, brief_ref: state.task.current_brief, analysis_ref: state.directions.find((item) => item.direction_id === state.task.selected_direction?.id && item.revision === state.task.selected_direction.revision)?.analysis_ref ?? null })}>{t("Generate production materials")}</button>{historyControl}</div></div>
      {!busy && <GenerationBlocker blocker={blocker} onNavigate={onNavigate} />}
      {actionError && <div className="error" role="alert">{t(actionError)}<ConnectionHelp message={actionError} /></div>}
      <p className="production-empty">{t("No production materials yet.")}</p>
    </>}
    {historyOpen && <SaveDialog title={t("Production history")} onClose={() => setHistoryOpen(false)}>
      {current && <div className="production-history-current"><h4>{current.brief?.title}</h4><p>{t("Brief r")}{current.brief?.revision} {t("· Storyboard r")}{current.storyboard?.revision}</p><details><summary>{t("Source versions")}</summary><p>{sourceSummary(current)}</p></details></div>}
      <SavedHistory state={state} busy={busy} onExport={(snapshot, format) => { setHistoryOpen(false); onExport(snapshot, format); }} />
      {!current && !state.production_briefs.length && !state.storyboards.length && <p>{t("No saved production versions yet.")}</p>}
      <button className="secondary" type="button" onClick={() => setHistoryOpen(false)}>{t("Close")}</button>
    </SaveDialog>}
    {historical && <SaveDialog title={t("Export a historical version?")} onClose={() => setHistorical(null)}><p>{productionStatus(historical.snapshot)}{t(". The filename and document will carry this label and the exact original source versions.")}</p><div className="actions"><button type="button" onClick={() => { performExport(historical.snapshot, historical.format); setHistorical(null); }}>{t("Export historical version")}</button><button type="button" className="secondary" onClick={() => setHistorical(null)}>{t("Cancel")}</button></div></SaveDialog>}
    {preview && <PdfPreview snapshot={preview} onClose={() => setPreview(null)} />}
  </section>;
}
