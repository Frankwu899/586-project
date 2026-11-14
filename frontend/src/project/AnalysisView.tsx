import { useEffect, useRef, useState } from 'react';
import LogicGraph from '../LogicGraph';
import type { StructureGraph } from '../structureApi';
import type { Analysis, Project, ReferenceStructure } from './contracts';
import { Badge, Empty, FailureNotice, Sources, date, type SourceAction } from './Common';
import type { Mutate } from './client';
import { failureMessage } from './status';


function excerpt(text: string, limit: number) {
  if (text.length <= limit) return text;
  const candidate = text.slice(0, limit);
  const boundary = Math.max(candidate.lastIndexOf('. '), candidate.lastIndexOf('。'), candidate.lastIndexOf(' '));
  return `${candidate.slice(0, boundary > limit / 2 ? boundary + 1 : limit).trimEnd()}…`;
}
function ReferenceGraph({ structure, project, onSource }: { structure: ReferenceStructure; project: Project; onSource: SourceAction }) {
  const [selected, setSelected] = useState<string | null>(null);
  const node = structure.nodes.find(item => item.id === selected);
  const graph: StructureGraph = {
    title: project.resources.find(item => item.id === structure.resource_id)?.name ?? 'Reference structure', summary: structure.summary,
    nodes: structure.nodes.map(item => ({ id: item.id, label: item.label, explanation: item.detail, kind: item.kind === 'interpretation' ? 'inference' : item.kind,
      event_ids: item.sources.flatMap(source => source.event_id ? [source.event_id] : []), source_ids: [], context_ids: [], moments: item.sources.flatMap(source => source.start_seconds != null ? [{ event_id: source.event_id ?? '', start_frame: null, end_frame: null, start_seconds: source.start_seconds, end_seconds: source.end_seconds ?? source.start_seconds, precision: 'interval' as const }] : []) })),
    edges: structure.edges.map((edge, index) => ({ id: `edge-${index}`, from_node: edge.source, to_node: edge.target, relation: edge.label, explanation: edge.explanation })), methods: [], research_gaps: [],
  };
  return <section className="va-structure"><p>{structure.summary}</p><LogicGraph graph={graph} selected={selected} onSelect={setSelected} chosen={[]} />
    {node ? <section className="va-node-detail" aria-label="Selected structure moment"><h3>{node.label}</h3><p>{node.detail}</p><Sources sources={node.sources} project={project} onSource={onSource} /></section> : <p className="va-muted">Select a node to inspect its explanation and source moments.</p>}
  </section>;
}
function Report({ analysis, project, onSource }: { analysis: Analysis; project: Project; onSource: SourceAction }) {
  const structures = analysis.structures ?? [];
  const [resourceId, setResourceId] = useState(structures[0]?.resource_id ?? '');
  const structure = structures.find(item => item.resource_id === resourceId) ?? structures[0];
  const insights = [...analysis.findings, ...analysis.opportunities].slice(0, 5);
  return <article className="va-analysis-report va-glass"><div className="va-section-heading"><div><span className="va-eyebrow">{analysis.inputs.resource_ids.length > 1 ? 'MULTIPLE REFERENCES' : 'REFERENCE ANALYSIS'}</span><p className="va-muted">Saved locally · {date(analysis.created_at)}</p></div><Badge tone={analysis.needs_review ? 'warning' : 'success'}>{analysis.needs_review ? 'Inputs changed · review' : 'Saved analysis'}</Badge></div><h2 className="va-analysis-conclusion">{excerpt(analysis.conclusion, 400)}</h2>{analysis.conclusion.length > 400 && <details><summary>Read full takeaway</summary><p>{analysis.conclusion}</p></details>}{analysis.inputs.visual_only && <p className="va-notice">Visual evidence only · speech was unavailable for this analysis.</p>}
    {structures.length > 1 && <label>Individual reference structure<select aria-label="Reference structure" value={structure?.resource_id ?? ''} onChange={event => setResourceId(event.target.value)}>{structures.map(item => <option key={item.resource_id} value={item.resource_id}>{project.resources.find(resource => resource.id === item.resource_id)?.name ?? 'Unavailable reference'}</option>)}</select></label>}
    {structure ? <ReferenceGraph key={structure.resource_id} structure={structure} project={project} onSource={onSource} /> : <p className="va-notice">This saved report has no structure graph. Its evidence remains available; a new analysis can add a grounded visual explanation.</p>}
    {!!insights.length && <section><h3>Key insights</h3><ul>{insights.map((insight, index) => <li key={index}>{excerpt(insight, 240)}{insight.length > 240 && <details><summary>Read full insight</summary><p>{insight}</p></details>}</li>)}</ul></section>}
    <details><summary>Patterns, comparisons and opportunities</summary><div className="va-analysis-columns"><section><h3>Shared patterns</h3><ul>{analysis.findings.map((item, index) => <li key={index}>{item}</li>)}</ul></section><section><h3>Differences</h3><ul>{analysis.differences.map((item, index) => <li key={index}>{item}</li>)}</ul></section></div><h3>Adaptation opportunities</h3><ul>{analysis.opportunities.map((item, index) => <li key={index}>{item}</li>)}</ul></details>
    <details><summary>Evidence and source moments</summary><Sources sources={analysis.sources} project={project} onSource={onSource} />{analysis.sources.map((source, index) => source.excerpt && <blockquote key={index}>{source.excerpt}</blockquote>)}</details>
    {analysis.limitations.length > 0 && <details><summary>Coverage and interpretation limits</summary><ul>{analysis.limitations.map((item, index) => <li key={index}>{failureMessage(item)}</li>)}</ul></details>}
  </article>;
}
export default function AnalysisView({ project, mutate, onSource, onResources }: { project: Project; mutate: Mutate; onSource: SourceAction; onResources: () => void }) {
  const activeScope = project.active_content_id ?? '';
  const previousActive = useRef(activeScope);
  const [scope, setScope] = useState(() => project.analyses.some(item => (item.content_id ?? '') === activeScope) ? activeScope : project.analyses.at(-1)?.content_id ?? activeScope);
  useEffect(() => { if (previousActive.current !== activeScope) { previousActive.current = activeScope; setScope(activeScope); } }, [activeScope]);
  const [historyId, setHistoryId] = useState('');
  const reports = project.analyses.filter(item => (item.content_id ?? '') === scope);
  const current = reports.at(-1);
  const report = reports.find(item => item.id === historyId) ?? current;
  const jobs = project.jobs.filter(job => job.kind === 'analyze' && (job.content_id ?? '') === scope);
  const lastJob = jobs.at(-1);
  const running = jobs.some(job => ['queued', 'running'].includes(job.status));
  return <section className="va-analysis"><div className="va-page-heading"><div><h1>Reference analysis</h1><p>See how each reference works, then compare the patterns.</p></div><button onClick={onResources}>Choose references</button></div>
    <label className="va-analysis-scope">Analysis for<select aria-label="Analysis scope" value={scope} onChange={event => { setHistoryId(''); setScope(event.target.value); void mutate('', { active_content_id: event.target.value || null }, 'PATCH'); }}><option value="">Project exploration{project.analyses.some(item => !item.content_id) ? ' · saved analysis' : ''}</option>{project.contents.map(item => <option key={item.id} value={item.id}>{item.title}{project.analyses.some(report => report.content_id === item.id) ? ' · saved analysis' : ''}</option>)}</select></label>
    {running && <div className="va-processing va-glass" role="status"><span className="va-spinner" /><p>{current ? 'Preparing a replacement. Your saved analysis remains available.' : 'Analyzing selected references…'}</p></div>}
    {lastJob?.status === 'failed' && <FailureNotice message={lastJob.error ?? 'Analysis could not finish. Retry from Resources.'} code={lastJob.error_code} detail={`Operation ${lastJob.id}. Code ${lastJob.error_code ?? 'unavailable'}. Previous saved analysis retained.`} />}
    {!report ? <Empty title="A conclusion grounded in your references"><p>Select videos in Resources, then choose Analyze selected. Saved analysis stays available when you reopen this project.</p><button className="va-primary" onClick={onResources}>Open resources</button></Empty> : <>{report !== current && <p className="va-notice">Viewing a historical result. <button onClick={() => setHistoryId('')}>Return to current analysis</button></p>}<Report key={report.id} analysis={report} project={project} onSource={onSource} />{reports.length > 1 && <details className="va-history"><summary>Earlier saved analyses · {reports.length - 1}</summary>{reports.slice(0, -1).reverse().map(item => <button key={item.id} onClick={() => setHistoryId(item.id)}>View saved analysis · {date(item.created_at)}</button>)}</details>}</>}
  </section>;
}
