import { useI18n } from './i18n';
import './researchTranslations';
import { incompleteChannels, channelLabels } from './AnalysisCoverage';
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import type { TaskState } from './generated/contracts';
import { Badge, Field, type Mutate } from './ui';
import { ConnectionHelp } from './ApiConnection';
import { structureApi, type StructureNode, type StructureState } from './structureApi';
import LogicGraph from './LogicGraph';
import './structure.css';

const kindLabels: Record<StructureNode['kind'], string> = { observation: 'Video observation', source_claim: 'Attributed claim', inference: 'Inference', user_context: 'Your context' };
const running = (result: StructureState | null) => result?.status === 'analyzing' || result?.status === 'researching' || result?.feedback_status === 'running';
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Could not complete the operation.';
const timeLabel = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
function stored(key: string) { try { return localStorage.getItem(key); } catch { return null; } }
function storedIds(key: string): string[] { try { const value: unknown = JSON.parse(stored(key) ?? '[]'); return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []; } catch { return []; } }
function save(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* Browser persistence can be restricted. */ } }

function StructureInspector({ children, onClose, width, onResize }: { children: ReactNode; onClose: () => void; width: number; onResize: (width: number) => void }) {
  const { t } = useI18n();
  const [narrow, setNarrow] = useState(() => window.matchMedia('(max-width: 900px)').matches);
  const dialog = useRef<HTMLDialogElement>(null);
  const dragging = useRef<{ x: number; width: number } | null>(null);
  useEffect(() => {
    const query = window.matchMedia('(max-width: 900px)');
    const changed = () => setNarrow(query.matches);
    query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, []);
  useEffect(() => { if (narrow && dialog.current && !dialog.current.open) dialog.current.showModal(); }, [narrow]);
  const header = <div className="structure-inspector-header"><button type="button" className="secondary" onClick={onClose}>{t('Close details')}</button></div>;
  if (narrow) return <dialog ref={dialog} className="structure-inspector structure-inspector-dialog" aria-label={t('Selected structure node')} onCancel={event => { event.preventDefault(); onClose(); }}>{header}{children}</dialog>;
  return <aside className="structure-inspector" aria-label={t('Selected structure node')}>
    <div className="structure-resizer" role="separator" aria-label={t('Resize node details')} aria-orientation="vertical" aria-valuemin={280} aria-valuemax={520} aria-valuenow={width} tabIndex={0} onKeyDown={event => {
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); onResize(Math.max(280, Math.min(520, width + (event.key === 'ArrowLeft' ? 20 : -20)))); }
      else if (event.key === 'Home') { event.preventDefault(); onResize(340); }
    }} onPointerDown={event => { dragging.current = { x: event.clientX, width }; event.currentTarget.setPointerCapture(event.pointerId); }} onPointerMove={event => { if (dragging.current) onResize(Math.max(280, Math.min(520, dragging.current.width + dragging.current.x - event.clientX))); }} onPointerUp={() => { dragging.current = null; }} onPointerCancel={() => { dragging.current = null; }} onLostPointerCapture={() => { dragging.current = null; }} />
    {header}{children}
  </aside>;
}

export default function StructureWorkspace({ state, onSeekEvidence, onUseInIdeas, onActivity, mutate }: { state: TaskState; mutate: Mutate; onSeekEvidence: (frame: number) => void; onUseInIdeas: () => void; onActivity: (running: boolean, label: string, error?: string) => void }) {
  const { t, language } = useI18n();
  const taskId = state.task.task_id;
  const [result, setResult] = useState<StructureState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const statusRef = useRef<StructureState['status'] | null>(null);
  const [notice, setNotice] = useState('');
  useEffect(() => { if (!notice) return; const timeout = setTimeout(() => setNotice(''), 6000); return () => clearTimeout(timeout); }, [notice]);
  const [selected, setSelected] = useState<string | null>(() => stored(`structure-node:${taskId}`));
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [inspectorWidth, setInspectorWidth] = useState(340);
  const [view, setView] = useState<'graph' | 'methods'>(() => stored(`structure-view:${taskId}`) === 'methods' ? 'methods' : 'graph');
  const [nodeIds, setNodeIds] = useState<string[]>(() => storedIds(`structure-chosen-nodes:${taskId}`));
  const [methodIds, setMethodIds] = useState<string[]>(() => storedIds(`structure-chosen-methods:${taskId}`));
  const [all, setAll] = useState(() => stored(`structure-chosen-all:${taskId}`) === 'true');
  const [instruction, setInstruction] = useState('');
  const [feedbackKind, setFeedbackKind] = useState<'question' | 'context' | 'reconsider'>('question');
  const [preview, setPreview] = useState<string | null>(null);
  const activityRef = useRef(onActivity);
  useEffect(() => { activityRef.current = onActivity; }, [onActivity]);
  const processing = running(result);
  const analysis = state.analyses.find((item) => item.analysis_id === state.task.current_analysis?.id && item.revision === state.task.current_analysis.revision);
  const source = state.videos.find((item) => item.video_id === state.task.current_video_id);
  const valid = Boolean(analysis && ['succeeded', 'partial'].includes(analysis.status) && analysis.events.length && !source?.deleted_at && source?.video_id === analysis.video_id);
  const outdated = Boolean(result && (result.outdated || result.analysis_ref.id !== analysis?.analysis_id || result.analysis_ref.revision !== analysis?.revision || result.video_id !== state.task.current_video_id));
  const graph = result?.graph;
  const differentLanguage = Boolean(result?.output_language && result.output_language !== language);
  const evidenceAnalysis = state.analyses.find((item) => item.analysis_id === result?.analysis_ref.id && item.revision === result?.analysis_ref.revision);
  const incomplete = evidenceAnalysis ? incompleteChannels(evidenceAnalysis) : [];
  const chosenNodes = nodeIds.filter((id) => graph?.nodes.some((item) => item.id === id));
  const chosenMethods = methodIds.filter((id) => graph?.methods.some((item) => item.id === id));
  useEffect(() => { save(`structure-chosen-nodes:${taskId}`, JSON.stringify(nodeIds)); save(`structure-chosen-methods:${taskId}`, JSON.stringify(methodIds)); save(`structure-chosen-all:${taskId}`, String(all)); save(`structure-view:${taskId}`, view); }, [taskId, nodeIds, methodIds, all, view]);
  const node = graph?.nodes.find((item) => item.id === selected);
  const locked = submitting || processing;
  useEffect(() => {
    let cancelled = false; let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const next = await structureApi.get(taskId);
        if (cancelled) return;
        if (statusRef.current === 'researching' && next && next.status !== 'researching') setNotice(next.status === 'ready' ? t("Research updated the analysis.") : t("Completed analysis is ready. Some background remains unverified."));
        statusRef.current = next?.status ?? null; setConnectionError('');
        setResult((previous) => previous && next?.structure_id === previous.structure_id && previous.version > next.version ? previous : next);
        setLoading(false);
        timer = setTimeout(poll, running(next) ? 1200 : 5000);
      } catch (failure) { if (!cancelled) { setConnectionError(messageOf(failure)); setLoading(false); timer = setTimeout(poll, 7000); } }
    };
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [taskId, t]);
  useEffect(() => { if (!result) return; activityRef.current(processing, result?.feedback_status === 'running' ? t("Reviewing Structure feedback") : result?.status === 'researching' ? t("Researching video context") : t("Analyzing Structure"), result?.error?.message); }, [processing, result, t]);
  useEffect(() => { setInstruction(stored(`structure-feedback:${taskId}:${node?.id ?? ''}`) ?? ''); }, [taskId, node?.id]);
  const chooseNode = (id: string) => { setSelected(id); setInspectorOpen(true); save(`structure-node:${taskId}`, id); };
  const closeInspector = () => {
    setInspectorOpen(false);
    if (selected) requestAnimationFrame(() => document.querySelector<HTMLButtonElement>(`[data-node-id="${CSS.escape(selected)}"]`)?.focus({ preventScroll: true }));
  };
  const run = async (action: () => Promise<void>) => { setSubmitting(true); setError(''); setNotice(''); try { await action(); } catch (failure) { setError(messageOf(failure)); } finally { setSubmitting(false); } };
  const analyze = () => run(async () => {
    let analysisRef = valid ? state.task.current_analysis : null;
    if (!analysisRef && source) {
      const recognized = await mutate('/recognize', { video_id: source.video_id });
      if (!recognized || !recognized.task.current_analysis) throw new Error(t("Video recognition did not complete. Open Timeline to review the source and try again."));
      analysisRef = recognized.task.current_analysis;
    }
    if (analysisRef) setResult(await structureApi.analyze(taskId, analysisRef));
  });
  const sendFeedback = () => run(async () => { if (!result || !node) return; setResult(await structureApi.feedback(taskId, result.version, node.id, instruction, feedbackKind)); setInstruction(''); save(`structure-feedback:${taskId}:${node.id}`, ''); });
  const transferToIdeas = () => run(async () => { if (!result) return; await structureApi.handoff(taskId, result.version, chosenNodes, chosenMethods, all); window.dispatchEvent(new CustomEvent('structure-handoff', { detail: { taskId } })); onUseInIdeas(); });
  const toggle = (id: string, values: string[], setter: (value: string[]) => void) => setter(values.includes(id) ? values.filter((value) => value !== id) : [...values, id]);
  return <section className="structure-workspace" aria-label={t("Structure analysis")}>
    <div className="structure-toolbar"><div><h2>{graph?.title || t("Structure")}</h2></div><div className="structure-actions">{result?.origin === 'sample' && <Badge warning>{t("Fictional sample")}</Badge>}{<button type="button" disabled={!source || source.intake_status !== 'ready' || Boolean(source.deleted_at) || locked || loading} onClick={() => void analyze()}>{submitting || result?.status === 'analyzing' ? t("Analyzing…") : outdated ? t("Analyze current version") : graph ? differentLanguage ? t("Generate in {language}", { language: t(language) }) : t("Analyze again") : t("Analyze structure")}</button>}{graph && <button type="button" disabled={locked || outdated || result?.source_deleted || (!all && !chosenNodes.length && !chosenMethods.length)} onClick={() => void transferToIdeas()}>{t("Use in Ideas")}{all ? t(" · All") : chosenNodes.length + chosenMethods.length ? ` · ${chosenNodes.length + chosenMethods.length}` : ''}</button>}{result?.proposals.some(proposal => proposal.status === 'pending') && <button className="secondary" type="button" onClick={() => setInspectorOpen(true)}>{t('Suggested update')}</button>}</div></div>
    {(error || connectionError || result?.error) ? <p className={`${!error && !connectionError && result?.status === 'partial' ? 'notice' : 'error'} structure-message`} role={!error && !connectionError && result?.status === 'partial' ? 'status' : 'alert'}>{error || connectionError || result?.error?.message}<ConnectionHelp message={error || connectionError || result?.error?.message} /></p>
      : processing && graph ? <p className="structure-message notice" role="status"><span className="spinner" aria-hidden="true" />{result?.feedback_status === 'running' ? t('Reviewing feedback…') : result?.status === 'researching' ? t('Researching background…') : t('Analyzing structure…')}</p>
      : outdated ? <p className="structure-message notice" role="status">{t('Reference changed. Analyze the current version to use this work in Ideas.')}</p>
      : graph && incomplete.length > 0 ? <div className="structure-message notice" role="status"><span>{t('Incomplete evidence: {channels}.', { channels: incomplete.map(kind => t(channelLabels[kind])).join(', ') })}</span><button className="text-button" type="button" onClick={() => onSeekEvidence(0)}>{t('Review missing evidence')}</button></div>
      : (notice || (result?.status === 'partial' && result.research_note)) ? <p className="structure-message" role="status">{notice || result?.research_note}</p> : null}
    {!graph ? <div className="structure-empty"><h3>{loading ? t('Opening saved research…') : processing ? t('Analyzing structure…') : !source || source.deleted_at ? t('Import a video to begin') : t('Ready to analyze')}</h3>{(!source || source.deleted_at) && <button className="secondary" type="button" onClick={() => onSeekEvidence(0)}>{t('Open Timeline')}</button>}</div> : <div className={`structure-content${inspectorOpen ? ' inspector-open' : ''}`} style={{ '--structure-inspector-width': `${inspectorWidth}px` } as CSSProperties}>
      <div className="structure-main"><div className="structure-viewbar"><div className="segmented"><button className="secondary" type="button" aria-pressed={view === 'graph'} onClick={() => setView('graph')}>{t("Logic map")}</button><button className="secondary" type="button" aria-pressed={view === 'methods'} onClick={() => setView('methods')}>{t("Transferable methods ·")} {graph.methods.length}</button></div><label><input type="checkbox" checked={all} onChange={(event) => setAll(event.target.checked)} /> {t("Select all for Ideas")}</label></div>{view === 'graph' ? <LogicGraph graph={graph} selected={node?.id ?? null} onSelect={chooseNode} chosen={all ? graph.nodes.map(item => item.id) : nodeIds} /> : <div className="structure-methods">{graph.methods.length ? graph.methods.map((method) => <article key={method.id}><label className="method-choice"><input type="checkbox" checked={all || methodIds.includes(method.id)} disabled={all} onChange={() => toggle(method.id, methodIds, setMethodIds)} /><strong>{method.title}</strong></label><p>{method.explanation}</p><h4>{t("Works when")}</h4><ul>{method.conditions.map((condition, index) => <li key={index}>{condition}</li>)}</ul><div className="method-nodes">{method.node_ids.map((id) => <button className="text-button" key={id} type="button" onClick={() => { chooseNode(id); setView('graph'); }}>{graph.nodes.find((item) => item.id === id)?.label ?? id} ↗</button>)}</div></article>) : <p className="muted">{t("No transferable method was supported in the completed analysis.")}</p>}</div>}</div>
      {inspectorOpen && <StructureInspector onClose={closeInspector} width={inspectorWidth} onResize={setInspectorWidth}>{node && <><div className={`structure-kind ${node.kind}`}>{t(kindLabels[node.kind])}</div><h3>{node.label}</h3><p>{node.explanation}</p><label className="node-choice"><input type="checkbox" checked={all || nodeIds.includes(node.id)} disabled={all} onChange={() => toggle(node.id, nodeIds, setNodeIds)} /> {t("Include in Ideas")}</label>
        {node.moments.length > 0 && <section className="node-evidence"><h4>{t("Video evidence")}</h4>{node.moments.map((moment, index) => { const evidence = evidenceAnalysis?.events.find((item) => item.event_id === moment.event_id); return <article key={`${moment.event_id}:${index}`}><button type="button" className="time" disabled={moment.start_frame === null || outdated || result?.source_deleted} onClick={() => moment.start_frame !== null && onSeekEvidence(moment.start_frame)}>{timeLabel(moment.start_seconds)}{moment.precision === 'interval' ? `–${timeLabel(moment.end_seconds)}` : t(" · Sample")} ↗</button>{evidence && <p>{evidence.text || evidence.description}</p>}</article>; })}</section>}
        {node.source_ids.length > 0 && <section className="node-sources"><h4>{t("Sources")}</h4>{node.source_ids.map((id) => { const item = result?.sources.find((source) => source.id === id); return item ? <article key={id}><a href={item.url} target="_blank" rel="noreferrer">{item.title} ↗</a><p>{item.claim}</p><small>{item.attribution}</small></article> : null; })}</section>}
        {node.context_ids.length > 0 && <section><h4>{t("Your context")}</h4>{node.context_ids.map((id) => <p key={id}>{result?.contexts.find((item) => item.id === id)?.text}</p>)}</section>}
        {graph.edges.filter((edge) => edge.from_node === node.id || edge.to_node === node.id).length > 0 && <section className="node-relations"><h4>{t("Connections")}</h4>{graph.edges.filter((edge) => edge.from_node === node.id || edge.to_node === node.id).map((edge) => { const other = edge.from_node === node.id ? edge.to_node : edge.from_node; return <div key={edge.id}><button type="button" className="text-button" onClick={() => chooseNode(other)}>{edge.from_node === node.id ? `${edge.relation} → ` : `← ${edge.relation} · `}{graph.nodes.find((item) => item.id === other)?.label}</button><p>{edge.explanation}</p></div>; })}</section>}
        <form className="node-feedback" onSubmit={(event) => { event.preventDefault(); void sendFeedback(); }}><Field label={t("Explore this node")}><select value={feedbackKind} onChange={(event) => setFeedbackKind(event.target.value as typeof feedbackKind)}><option value="question">{t("Ask a question")}</option><option value="context">{t("Add context")}</option><option value="reconsider">{t("Ask for a correction")}</option></select></Field><Field label={feedbackKind === 'question' ? t("Your question") : feedbackKind === 'context' ? t("Additional context") : t("What needs reconsidering?")}><textarea value={instruction} onChange={(event) => { setInstruction(event.target.value); save(`structure-feedback:${taskId}:${node.id}`, event.target.value); }} placeholder={t("What connects this moment to the main message?")} maxLength={8000} /></Field><button type="submit" disabled={!instruction.trim() || locked || outdated || result?.source_deleted}>{result?.feedback_status === 'running' ? t("Reviewing…") : t("Send to agent")}</button></form>
        {result?.answers.filter((answer) => answer.node_id === node.id).map((answer) => <article className="structure-answer" key={answer.id}><strong>{answer.question}</strong><p>{answer.answer}</p></article>)}
      </>}{result?.proposals.filter((proposal) => proposal.status === 'pending').map((proposal) => <section className="structure-proposal" key={proposal.id}><h4>{t("Suggested update")}</h4><p>{proposal.reason}</p><button type="button" className="secondary" onClick={() => setPreview(preview === proposal.id ? null : proposal.id)}>{preview === proposal.id ? t("Close preview") : t("Preview changes")}</button>{preview === proposal.id && <div className="proposal-preview">{proposal.affected_node_ids.map((id) => { const current = graph.nodes.find((item) => item.id === id); const suggested = proposal.graph.nodes.find((item) => item.id === id); return <article key={id}>{current && <><small>{t("Current")}</small><strong>{current.label}</strong><p>{current.explanation}</p></>}<small>{t("Suggested")}</small>{suggested ? <><strong>{suggested.label}</strong><p>{suggested.explanation}</p></> : <p>{t("This node is removed from the suggested structure.")}</p>}</article>; })}{proposal.graph.edges.filter((edge) => proposal.affected_node_ids.includes(edge.from_node) || proposal.affected_node_ids.includes(edge.to_node)).map((edge) => <p key={edge.id}><strong>{edge.relation}</strong> · {edge.explanation}</p>)}<button type="button" disabled={locked || outdated} onClick={() => void run(async () => { if (result) { setResult(await structureApi.adopt(taskId, result.version, proposal.id)); setPreview(null); setNotice(t("Suggested changes adopted.")); } })}>{t("Adopt update")}</button></div>}</section>)}</StructureInspector>}
    </div>}
  </section>;
}
