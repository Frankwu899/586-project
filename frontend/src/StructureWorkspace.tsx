import { useEffect, useRef, useState } from 'react';
import type { TaskState } from './generated/contracts';
import { Badge, Field, type Mutate } from './ui';
import { structureApi, type StructureGraph, type StructureNode, type StructureState } from './structureApi';
import './structure.css';

const kindLabels: Record<StructureNode['kind'], string> = { observation: 'Video observation', source_claim: 'Attributed claim', inference: 'Inference', user_context: 'Your context' };
const running = (result: StructureState | null) => result?.status === 'analyzing' || result?.status === 'researching' || result?.feedback_status === 'running';
const messageOf = (error: unknown) => error instanceof Error ? error.message : 'Could not complete the operation.';
const timeLabel = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;
function stored(key: string) { try { return localStorage.getItem(key); } catch { return null; } }
function storedIds(key: string): string[] { try { const value: unknown = JSON.parse(stored(key) ?? '[]'); return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []; } catch { return []; } }
function save(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* Browser persistence can be restricted. */ } }

function positionsFor(graph: StructureGraph) {
  const levels = new Map<string, number>();
  const remaining = new Set(graph.nodes.map((node) => node.id));
  // Bounded topological placement. Cyclic relationships still remain visible.
  for (let pass = 0; pass < graph.nodes.length && remaining.size; pass++) {
    let changed = false;
    for (const id of remaining) {
      const incoming = graph.edges.filter((edge) => edge.to_node === id).map((edge) => edge.from_node);
      if (incoming.some((source) => !levels.has(source))) continue;
      levels.set(id, Math.min(3, incoming.length ? Math.max(...incoming.map((source) => levels.get(source)!)) + 1 : 0));
      remaining.delete(id); changed = true;
    }
    if (!changed) break;
  }
  for (const id of remaining) levels.set(id, 0);
  const rows = [0, 0, 0, 0];
  const positions = new Map(graph.nodes.map((node) => { const column = levels.get(node.id)!; return [node.id, { x: 24 + column * 300, y: 26 + rows[column]++ * 174 }]; }));
  return { positions, width: Math.max(...[...levels.values()].map((level) => (level + 1) * 300)) + 20, height: Math.max(...rows) * 174 + 30 };
}

function LogicGraph({ graph, selected, onSelect, chosen }: { graph: StructureGraph; selected: string | null; onSelect: (id: string) => void; chosen: string[] }) {
  const layout = positionsFor(graph);
  return <div className="logic-viewport" tabIndex={0} role="region" aria-label="Video logic graph. Scroll to explore, or use Tab to select a node."><div className="logic-canvas" style={{ width: layout.width, height: layout.height }}><svg width={layout.width} height={layout.height} className="logic-connections" aria-hidden="true"><defs><marker id="structure-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7" fill="#73938f" /></marker></defs>{graph.edges.map((edge) => { const from = layout.positions.get(edge.from_node)!; const to = layout.positions.get(edge.to_node)!; const sameColumn = from.x === to.x; const startX = from.x + (sameColumn ? 110 : 220); const startY = from.y + (sameColumn ? 128 : 64); const endX = to.x + (sameColumn ? 110 : 0); const endY = to.y + (sameColumn ? 0 : 64); const bend = Math.max(28, Math.abs(endX - startX) / 2); return <g key={edge.id}><path d={sameColumn ? `M${startX},${startY} C${startX + 115},${startY + 25} ${endX + 115},${endY - 25} ${endX},${endY}` : `M${startX},${startY} C${startX + bend},${startY} ${endX - bend},${endY} ${endX},${endY}`} fill="none" stroke="#8ca7a3" strokeWidth="1.5" markerEnd="url(#structure-arrow)" /><text x={sameColumn ? startX + 94 : (startX + endX) / 2} y={(startY + endY) / 2 - 7} textAnchor="middle" className="relationship-label">{edge.relation.length > 16 ? `${edge.relation.slice(0, 15)}…` : edge.relation}</text></g>; })}</svg>{graph.nodes.map((node) => { const pos = layout.positions.get(node.id)!; return <button key={node.id} type="button" className={`logic-node ${node.kind} ${node.id === selected ? 'selected' : ''}`} style={{ left: pos.x, top: pos.y }} onClick={() => onSelect(node.id)} aria-pressed={node.id === selected}><span className="node-kind">{kindLabels[node.kind]}{chosen.includes(node.id) ? ' · Selected for Ideas' : ''}</span><strong>{node.label}</strong><span className="node-time">{node.moments.length ? [...new Set(node.moments.map((moment) => timeLabel(moment.start_seconds)))].join(' · ') : 'Background context'}</span></button>; })}</div></div>;
}

export default function StructureWorkspace({ state, onSeekEvidence, onUseInIdeas, onActivity, mutate }: { state: TaskState; mutate: Mutate; onSeekEvidence: (frame: number) => void; onUseInIdeas: () => void; onActivity: (running: boolean, label: string, error?: string) => void }) {
  const taskId = state.task.task_id;
  const [result, setResult] = useState<StructureState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const statusRef = useRef<StructureState['status'] | null>(null);
  const [notice, setNotice] = useState('');
  const [selected, setSelected] = useState<string | null>(() => stored(`structure-node:${taskId}`));
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
  const evidenceAnalysis = state.analyses.find((item) => item.analysis_id === result?.analysis_ref.id && item.revision === result?.analysis_ref.revision);
  const chosenNodes = nodeIds.filter((id) => graph?.nodes.some((item) => item.id === id));
  const chosenMethods = methodIds.filter((id) => graph?.methods.some((item) => item.id === id));
  useEffect(() => { save(`structure-chosen-nodes:${taskId}`, JSON.stringify(nodeIds)); save(`structure-chosen-methods:${taskId}`, JSON.stringify(methodIds)); save(`structure-chosen-all:${taskId}`, String(all)); save(`structure-view:${taskId}`, view); }, [taskId, nodeIds, methodIds, all, view]);
  const node = graph?.nodes.find((item) => item.id === selected) ?? graph?.nodes[0];
  const locked = submitting || processing;
  useEffect(() => {
    let cancelled = false; let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const next = await structureApi.get(taskId);
        if (cancelled) return;
        if (statusRef.current === 'researching' && next && next.status !== 'researching') setNotice(next.status === 'ready' ? 'Research updated the analysis.' : 'Completed analysis is ready. Some background remains unverified.');
        statusRef.current = next?.status ?? null; setConnectionError('');
        setResult((previous) => previous && next?.structure_id === previous.structure_id && previous.version > next.version ? previous : next);
        setLoading(false);
        timer = setTimeout(poll, running(next) ? 1200 : 5000);
      } catch (failure) { if (!cancelled) { setConnectionError(messageOf(failure)); setLoading(false); timer = setTimeout(poll, 7000); } }
    };
    void poll();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [taskId]);
  useEffect(() => { if (!result) return; activityRef.current(processing, result?.feedback_status === 'running' ? 'Reviewing Structure feedback' : result?.status === 'researching' ? 'Researching video context' : 'Analyzing Structure', result?.error?.message); }, [processing, result]);
  useEffect(() => { setInstruction(stored(`structure-feedback:${taskId}:${node?.id ?? ''}`) ?? ''); }, [taskId, node?.id]);
  const chooseNode = (id: string) => { setSelected(id); save(`structure-node:${taskId}`, id); };
  const run = async (action: () => Promise<void>) => { setSubmitting(true); setError(''); setNotice(''); try { await action(); } catch (failure) { setError(messageOf(failure)); } finally { setSubmitting(false); } };
  const analyze = () => run(async () => {
    let analysisRef = valid ? state.task.current_analysis : null;
    if (!analysisRef && source) {
      const recognized = await mutate('/recognize', { video_id: source.video_id });
      if (!recognized || !recognized.task.current_analysis) throw new Error('Video recognition did not complete. Open Timeline to review the source and try again.');
      analysisRef = recognized.task.current_analysis;
    }
    if (analysisRef) setResult(await structureApi.analyze(taskId, analysisRef));
  });
  const sendFeedback = () => run(async () => { if (!result || !node) return; setResult(await structureApi.feedback(taskId, result.version, node.id, instruction, feedbackKind)); setInstruction(''); save(`structure-feedback:${taskId}:${node.id}`, ''); });
  const transferToIdeas = () => run(async () => { if (!result) return; await structureApi.handoff(taskId, result.version, chosenNodes, chosenMethods, all); window.dispatchEvent(new CustomEvent('structure-handoff', { detail: { taskId } })); onUseInIdeas(); });
  const toggle = (id: string, values: string[], setter: (value: string[]) => void) => setter(values.includes(id) ? values.filter((value) => value !== id) : [...values, id]);
  return <section className="structure-workspace" aria-label="Structure analysis">
    <div className="structure-toolbar"><div><h2>Structure</h2><span className="muted">How the video builds its meaning.</span></div><div className="structure-actions">{result?.origin === 'sample' && <Badge warning>Fictional sample</Badge>}{(!result || outdated || result.status === 'failed') && <button type="button" disabled={!source || source.intake_status !== 'ready' || Boolean(source.deleted_at) || locked || loading} onClick={() => void analyze()}>{submitting || result?.status === 'analyzing' ? 'Analyzing…' : outdated ? 'Analyze current version' : 'Analyze structure'}</button>}{graph && <button type="button" disabled={locked || outdated || result?.source_deleted || (!all && !chosenNodes.length && !chosenMethods.length)} onClick={() => void transferToIdeas()}>Use in Ideas{all ? ' · All' : chosenNodes.length + chosenMethods.length ? ` · ${chosenNodes.length + chosenMethods.length}` : ''}</button>}</div></div>
    {(error || connectionError || result?.error) && <p className={`${!error && !connectionError && result?.status === 'partial' ? 'notice' : 'error'} structure-message`} role={!error && !connectionError && result?.status === 'partial' ? 'status' : 'alert'}>{error || connectionError || result?.error?.message}</p>}
    {(processing || notice || result?.research_note || outdated) && <p className="structure-message notice" role="status">{processing && <span className="spinner" aria-hidden="true" />}{processing ? result?.feedback_status === 'running' ? 'Reviewing your feedback. Your current analysis stays available.' : result?.status === 'researching' ? 'Video-based draft is ready. Researching relevant background…' : 'Building the video logic graph…' : outdated ? 'This analysis belongs to an earlier reference version. Saved research remains available.' : notice || result?.research_note}</p>}
    {!graph ? <div className="structure-empty"><svg width="120" height="84" viewBox="0 0 120 84" aria-hidden="true"><path d="M28 42H59M60 42L89 17M60 42L89 67" stroke="#86aaa4" fill="none" strokeWidth="2"/><rect x="2" y="27" width="35" height="30" rx="7" fill="#dcece7"/><rect x="83" y="2" width="35" height="30" rx="7" fill="#e5e3f4"/><rect x="83" y="52" width="35" height="30" rx="7" fill="#dcece7"/></svg><h3>{loading ? 'Opening saved research…' : processing ? 'Understanding this video…' : 'See how the pieces connect'}</h3><p>{!source || source.deleted_at ? 'Import a video in Timeline to begin. No brand brief is required.' : 'The agent explains the narrative, checks relevant background, and identifies methods you can borrow.'}</p>{(!source || source.deleted_at) && <button className="secondary" type="button" onClick={() => onSeekEvidence(0)}>Open Timeline</button>}</div> : <div className="structure-content">
      <div className="structure-main"><div className="structure-summary"><h3>{graph.title}</h3><p>{graph.summary}</p></div><div className="structure-viewbar"><div className="segmented"><button className="secondary" type="button" aria-pressed={view === 'graph'} onClick={() => setView('graph')}>Logic map</button><button className="secondary" type="button" aria-pressed={view === 'methods'} onClick={() => setView('methods')}>Transferable methods · {graph.methods.length}</button></div><label><input type="checkbox" checked={all} onChange={(event) => setAll(event.target.checked)} /> Select all for Ideas</label></div>{view === 'graph' ? <LogicGraph graph={graph} selected={node?.id ?? null} onSelect={chooseNode} chosen={nodeIds} /> : <div className="structure-methods">{graph.methods.length ? graph.methods.map((method) => <article key={method.id}><label className="method-choice"><input type="checkbox" checked={all || methodIds.includes(method.id)} disabled={all} onChange={() => toggle(method.id, methodIds, setMethodIds)} /><strong>{method.title}</strong></label><p>{method.explanation}</p><h4>Works when</h4><ul>{method.conditions.map((condition, index) => <li key={index}>{condition}</li>)}</ul><div className="method-nodes">{method.node_ids.map((id) => <button className="text-button" key={id} type="button" onClick={() => { chooseNode(id); setView('graph'); }}>{graph.nodes.find((item) => item.id === id)?.label ?? id} ↗</button>)}</div></article>) : <p className="muted">No transferable method was supported in the completed analysis.</p>}</div>}</div>
      <aside className="structure-inspector" aria-label="Selected structure node">{node && <><div className={`structure-kind ${node.kind}`}>{kindLabels[node.kind]}</div><h3>{node.label}</h3><p>{node.explanation}</p>{node.kind === 'inference' && <p className="inference-note">An interpretation of the available evidence, not a verified intent or measured effect.</p>}<label className="node-choice"><input type="checkbox" checked={all || nodeIds.includes(node.id)} disabled={all} onChange={() => toggle(node.id, nodeIds, setNodeIds)} /> Include in Ideas</label>
        {node.moments.length > 0 && <section className="node-evidence"><h4>Video evidence</h4>{node.moments.map((moment, index) => { const evidence = evidenceAnalysis?.events.find((item) => item.event_id === moment.event_id); return <article key={`${moment.event_id}:${index}`}><button type="button" className="time" disabled={moment.start_frame === null || outdated || result?.source_deleted} onClick={() => moment.start_frame !== null && onSeekEvidence(moment.start_frame)}>{timeLabel(moment.start_seconds)}{moment.precision === 'interval' ? `–${timeLabel(moment.end_seconds)}` : ' · Sample'} ↗</button>{evidence && <p>{evidence.text || evidence.description}</p>}</article>; })}</section>}
        {node.source_ids.length > 0 && <section className="node-sources"><h4>Sources</h4>{node.source_ids.map((id) => { const item = result?.sources.find((source) => source.id === id); return item ? <article key={id}><a href={item.url} target="_blank" rel="noreferrer">{item.title} ↗</a><p>{item.claim}</p><small>{item.attribution}</small></article> : null; })}</section>}
        {node.context_ids.length > 0 && <section><h4>Your context</h4>{node.context_ids.map((id) => <p key={id}>{result?.contexts.find((item) => item.id === id)?.text}</p>)}</section>}
        {graph.edges.filter((edge) => edge.from_node === node.id || edge.to_node === node.id).length > 0 && <section className="node-relations"><h4>Connections</h4>{graph.edges.filter((edge) => edge.from_node === node.id || edge.to_node === node.id).map((edge) => { const other = edge.from_node === node.id ? edge.to_node : edge.from_node; return <div key={edge.id}><button type="button" className="text-button" onClick={() => chooseNode(other)}>{edge.relation} → {graph.nodes.find((item) => item.id === other)?.label}</button><p>{edge.explanation}</p></div>; })}</section>}
        <form className="node-feedback" onSubmit={(event) => { event.preventDefault(); void sendFeedback(); }}><Field label="Explore this node"><select value={feedbackKind} onChange={(event) => setFeedbackKind(event.target.value as typeof feedbackKind)}><option value="question">Ask a question</option><option value="context">Add context</option><option value="reconsider">Ask for a correction</option></select></Field><Field label={feedbackKind === 'question' ? 'Your question' : feedbackKind === 'context' ? 'Additional context' : 'What needs reconsidering?'}><textarea value={instruction} onChange={(event) => { setInstruction(event.target.value); save(`structure-feedback:${taskId}:${node.id}`, event.target.value); }} placeholder="What connects this moment to the main message?" maxLength={8000} /></Field><button type="submit" disabled={!instruction.trim() || locked || outdated || result?.source_deleted}>{result?.feedback_status === 'running' ? 'Reviewing…' : 'Send to agent'}</button></form>
        {result?.answers.filter((answer) => answer.node_id === node.id).map((answer) => <article className="structure-answer" key={answer.id}><strong>{answer.question}</strong><p>{answer.answer}</p></article>)}
      </>}{result?.proposals.filter((proposal) => proposal.status === 'pending').map((proposal) => <section className="structure-proposal" key={proposal.id}><h4>Suggested update</h4><p>{proposal.reason}</p><button type="button" className="secondary" onClick={() => setPreview(preview === proposal.id ? null : proposal.id)}>{preview === proposal.id ? 'Close preview' : 'Preview changes'}</button>{preview === proposal.id && <div className="proposal-preview">{proposal.affected_node_ids.map((id) => { const current = graph.nodes.find((item) => item.id === id); const suggested = proposal.graph.nodes.find((item) => item.id === id); return <article key={id}>{current && <><small>Current</small><strong>{current.label}</strong><p>{current.explanation}</p></>}<small>Suggested</small>{suggested ? <><strong>{suggested.label}</strong><p>{suggested.explanation}</p></> : <p>This node is removed from the suggested structure.</p>}</article>; })}{proposal.graph.edges.filter((edge) => proposal.affected_node_ids.includes(edge.from_node) || proposal.affected_node_ids.includes(edge.to_node)).map((edge) => <p key={edge.id}><strong>{edge.relation}</strong> · {edge.explanation}</p>)}<button type="button" disabled={locked || outdated} onClick={() => void run(async () => { if (result) { setResult(await structureApi.adopt(taskId, result.version, proposal.id)); setPreview(null); setNotice('Suggested changes adopted.'); } })}>Adopt update</button></div>}</section>)}</aside>
    </div>}
  </section>;
}
