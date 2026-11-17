import { useEffect, useRef, useState } from 'react';
import LogicGraph from '../LogicGraph';
import type { StructureGraph } from '../structureApi';
import type { Analysis, AnalysisInsight, Project, ReferenceStructure, SourceRef } from './contracts';
import { Badge, Empty, FailureNotice, Sources, date, type SourceAction } from './Common';
import type { Mutate } from './client';
import { failureMessage } from './status';
import './analysis.css';

const kindLabel = { observation: 'Video observation', interpretation: 'Interpretation', source_claim: 'Attributed claim', user_context: 'Your context' };
const unique = (items: string[]) => [...new Set(items.map(item => item.trim()).filter(Boolean))];

function sourceMoment(project: Project, source: SourceRef) {
  if (source.start_seconds == null) return [];
  const resource = project.resources.find(item => item.id === source.resource_id);
  const revision = source.evidence_revision != null ? resource?.evidence.find(item => item.revision === source.evidence_revision) : undefined;
  const event = revision?.events.find(item => item.id === source.event_id);
  return [{ event_id: source.event_id ?? '', start_frame: event?.start_frame ?? null, end_frame: event?.end_frame ?? null,
    start_seconds: source.start_seconds, end_seconds: source.end_seconds ?? source.start_seconds,
    precision: event?.precision === 'interval' ? 'interval' as const : 'sample' as const }];
}

function ReferenceGraph({ structure, project, onSource }: { structure: ReferenceStructure; project: Project; onSource: SourceAction }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [asList, setAsList] = useState(false);
  const node = structure.nodes.find(item => item.id === selected);
  const graph: StructureGraph = {
    title: project.resources.find(item => item.id === structure.resource_id)?.name ?? 'Reference structure', summary: structure.summary,
    nodes: structure.nodes.map(item => ({ id: item.id, label: item.label, explanation: item.detail, kind: item.kind === 'interpretation' ? 'inference' : item.kind,
      event_ids: item.sources.flatMap(source => source.event_id ? [source.event_id] : []), source_ids: [], context_ids: [], moments: item.sources.flatMap(source => sourceMoment(project, source)) })),
    edges: structure.edges.map((edge, index) => ({ id: `edge-${index}`, from_node: edge.source, to_node: edge.target, relation: edge.label, explanation: edge.explanation })), methods: [], research_gaps: [],
  };
  return <section className="va-structure" aria-label="Reference structure details">
    <div className="va-structure-description"><details><summary>Source structure context</summary><p>{structure.summary}</p></details><button type="button" aria-pressed={asList} onClick={() => setAsList(!asList)}>{asList ? 'View as graph' : 'View as list'}</button></div>
    <div hidden={asList}><LogicGraph graph={graph} selected={selected} onSelect={setSelected} chosen={[]} initialFit /></div>
    {asList && <ol className="va-structure-list" aria-label="Structure as list">{structure.nodes.map(item => <li key={item.id}><span className="va-structure-kind">{kindLabel[item.kind]}</span><button type="button" className="va-structure-list-title" aria-pressed={selected === item.id} onClick={() => setSelected(item.id)}>{item.label}</button><p>{item.detail}</p><Sources sources={item.sources} project={project} onSource={onSource} />{structure.edges.filter(edge => edge.source === item.id).map((edge, index) => <p className="va-structure-list-edge" key={index}><strong>{edge.label} → {structure.nodes.find(target => target.id === edge.target)?.label ?? 'Saved node'}</strong><span>{edge.explanation}</span></p>)}</li>)}</ol>}
    {!asList && (node ? <section className="va-node-detail" aria-label="Selected structure moment"><div className="va-section-heading"><h3>{node.label}</h3><Badge>{kindLabel[node.kind]}</Badge></div><p>{node.detail}</p><Sources sources={node.sources} project={project} onSource={onSource} /></section> : <p className="va-muted">Select a node to inspect its function and source moments. Use View as list for a linear reading order.</p>)}
  </section>;
}

function Report({ analysis, project, mutate, onSource, onContent }: { analysis: Analysis; project: Project; mutate: Mutate; onSource: SourceAction; onContent?: () => void }) {
  const structures = analysis.structures ?? [];
  const [resourceId, setResourceId] = useState(structures[0]?.resource_id ?? '');
  const [savingInsight, setSavingInsight] = useState<string | null>(null);
  const structure = structures.find(item => item.resource_id === resourceId) ?? structures[0];
  const insightKeys = new Set<string>();
  const insights = (analysis.key_insights ?? []).filter(item => {
    const key = `${item.observation.trim().toLocaleLowerCase()}\n${item.application.trim().toLocaleLowerCase()}`;
    if (insightKeys.has(key)) return false;
    insightKeys.add(key); return true;
  }).slice(0, 5);
  const legacyNotes = !insights.length ? unique([...analysis.findings, ...analysis.opportunities]).slice(0, 5) : [];
  const insightText = new Set([...insights.flatMap(item => [item.observation.trim(), item.application.trim()]), ...legacyNotes]);
  const patterns = unique(analysis.findings).filter(item => !insightText.has(item));
  const opportunities = unique(analysis.opportunities).filter(item => !insightText.has(item));
  const multiple = analysis.inputs.resource_ids.length > 1;
  const sendInspiration = async (insight: AnalysisInsight) => {
    if (savingInsight !== null || !onContent) return;
    setSavingInsight(insight.id);
    try {
      const scope = 'content-inspiration';
      const saved = await mutate('', { editor_drafts: { [scope]: { analysis_id: analysis.id, insight_id: insight.id, observation: insight.observation, application: insight.application, sources: insight.sources } }, expected_editor_versions: { [scope]: project.editor_draft_versions[scope] ?? 0 } }, 'PATCH');
      if (saved) onContent();
    } finally { setSavingInsight(null); }
  };
  return <article className="va-analysis-report va-glass">
    <div className="va-analysis-receipt"><p>{analysis.inputs.resource_ids.length} {analysis.inputs.resource_ids.length === 1 ? 'reference' : 'references'} · Saved locally · {date(analysis.created_at)}</p><Badge tone={analysis.needs_review ? 'warning' : 'success'}>{analysis.needs_review ? 'Inputs changed · review' : 'Saved analysis'}</Badge></div>
    {analysis.inputs.visual_only && <p className="va-notice">Visual evidence only · speech was unavailable for this analysis.</p>}
    <section className="va-key-insights" aria-labelledby={`insights-${analysis.id}`}><h2 id={`insights-${analysis.id}`}>Key insights</h2>
      {insights.length > 0 ? <ol>{insights.map(insight => <li key={insight.id}><section aria-label={`Insight: ${insight.observation}`}><div className="va-insight-copy"><h3>{insight.observation}</h3><p>{insight.application}</p></div><div className="va-insight-actions"><Sources sources={insight.sources} project={project} onSource={onSource} />{!insight.sources.length && <p className="va-muted">This saved insight has no individually linked source.</p>}{onContent && <button type="button" disabled={savingInsight !== null} onClick={() => void sendInspiration(insight)}>{savingInsight === insight.id ? 'Saving inspiration…' : 'Use insight in Content plan'}</button>}</div></section></li>)}</ol> : <><p className="va-legacy-insight-note">This saved report has no individually linked insights. Its notes remain available below; source links are preserved in the graph and evidence details.</p>{legacyNotes.length > 0 ? <ul className="va-legacy-insights">{legacyNotes.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p className="va-muted">No separate insight notes were recorded. The original report remains available in Saved report context.</p>}</>}
    </section>
    {multiple && <section className="va-analysis-comparison" aria-labelledby={`comparison-${analysis.id}`}><h2 id={`comparison-${analysis.id}`}>Comparison</h2><p className="va-muted">Saved observations across the selected references; no effectiveness or statistical trend is implied.</p><div className="va-analysis-columns"><section><h3>Shared mechanisms</h3>{patterns.length ? <ul>{patterns.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No additional shared mechanisms were recorded.</p>}</section><section><h3>Differences</h3>{analysis.differences.length ? <ul>{analysis.differences.map((item, index) => <li key={index}>{item}</li>)}</ul> : <p>No supported differences were recorded.</p>}</section></div>{opportunities.length > 0 && <details><summary>Applications and conditions</summary><ul>{opportunities.map((item, index) => <li key={index}>{item}</li>)}</ul></details>}</section>}
    <section className="va-analysis-structure" aria-labelledby={`structure-${analysis.id}`}><div className="va-section-heading"><h2 id={`structure-${analysis.id}`}>Structure flow</h2>{structures.length > 1 && <label>Source<select aria-label="Reference structure" value={structure?.resource_id ?? ''} onChange={event => setResourceId(event.target.value)}>{structures.map(item => <option key={item.resource_id} value={item.resource_id}>{project.resources.find(resource => resource.id === item.resource_id)?.name ?? 'Unavailable reference'}</option>)}</select></label>}</div>{structure ? <ReferenceGraph key={structure.resource_id} structure={structure} project={project} onSource={onSource} /> : <p className="va-notice">This saved report has no structure graph. Its evidence remains available. No structure was invented from the old summary.</p>}</section>
    <details className="va-analysis-context"><summary>Saved report context</summary><p>{analysis.conclusion}</p>{!multiple && <><h3>Saved patterns and applications</h3><ul>{unique([...analysis.findings, ...analysis.differences, ...analysis.opportunities]).filter(item => !legacyNotes.includes(item)).map((item, index) => <li key={index}>{item}</li>)}</ul></>}</details>
    <details className="va-analysis-evidence"><summary>Evidence and source moments</summary><Sources sources={analysis.sources} project={project} onSource={onSource} />{analysis.sources.map((source, index) => source.excerpt && <blockquote key={index}>{source.excerpt}</blockquote>)}</details>
    {analysis.limitations.length > 0 && <details className="va-analysis-limits"><summary>Coverage and interpretation limits</summary><ul>{analysis.limitations.map((item, index) => <li key={index}>{failureMessage(item)}</li>)}</ul></details>}
  </article>;
}

export default function AnalysisView({ project, mutate, onSource, onResources, onContent }: { project: Project; mutate: Mutate; onSource: SourceAction; onResources: () => void; onContent?: () => void }) {
  const activeScope = project.active_content_id ?? '';
  const previousActive = useRef(activeScope);
  const [scope, setScope] = useState(() => {
    const latestReport = project.analyses.at(-1);
    return project.analyses.some(item => (item.content_id ?? '') === activeScope) ? activeScope : latestReport ? latestReport.content_id ?? '' : activeScope;
  });
  const [historyId, setHistoryId] = useState('');
  useEffect(() => { if (previousActive.current !== activeScope) { previousActive.current = activeScope; setScope(activeScope); setHistoryId(''); } }, [activeScope]);
  const reports = project.analyses.filter(item => (item.content_id ?? '') === scope);
  const current = reports.at(-1);
  const report = reports.find(item => item.id === historyId) ?? current;
  const jobs = project.jobs.filter(job => job.kind === 'analyze' && (job.content_id ?? '') === scope);
  const lastJob = jobs.at(-1);
  const running = jobs.some(job => ['queued', 'running'].includes(job.status));
  return <section className="va-analysis"><div className="va-page-heading"><div><h1>Reference analysis</h1><p>Understand the methods worth borrowing, then inspect their evidence.</p></div><button type="button" onClick={onResources}>Choose references</button></div>
    <div className="va-analysis-browse"><label className="va-analysis-scope">Analysis for<select aria-label="Analysis scope" value={scope} onChange={event => { setHistoryId(''); setScope(event.target.value); }}><option value="">Project exploration{project.analyses.some(item => !item.content_id) ? ' · saved analysis' : ''}</option>{project.contents.map(item => <option key={item.id} value={item.id}>{item.title}{project.analyses.some(saved => saved.content_id === item.id) ? ' · saved analysis' : ''}</option>)}</select></label><p>Browsing reports keeps your planned Video selected for Production.</p></div>
    {running && <div className="va-processing va-glass" role="status"><span className="va-spinner" /><p>{current ? 'Preparing a replacement. Your saved analysis remains available.' : 'Analyzing selected references…'}</p></div>}
    {lastJob?.status === 'failed' && <FailureNotice message={lastJob.error ?? 'Analysis could not finish. Retry from Resources.'} code={lastJob.error_code} detail={`Operation ${lastJob.id}. Code ${lastJob.error_code ?? 'unavailable'}. Previous saved analysis retained.`} />}
    {!report ? <Empty title="A conclusion grounded in your references"><p>Select files in Media Pool, then confirm the references to analyze. Saved analysis stays available when you reopen this project.</p><button type="button" className="va-primary" onClick={onResources}>Open resources</button></Empty> : <>{report !== current && <p className="va-notice">Viewing a historical result. <button type="button" onClick={() => setHistoryId('')}>Return to current analysis</button></p>}<Report key={report.id} analysis={report} project={project} mutate={mutate} onSource={onSource} onContent={onContent} />{reports.length > 1 && <details className="va-history"><summary>Earlier saved analyses · {reports.length - 1}</summary>{reports.slice(0, -1).reverse().map(item => <button type="button" key={item.id} onClick={() => setHistoryId(item.id)}>View saved analysis · {date(item.created_at)}</button>)}</details>}</>}
  </section>;
}
