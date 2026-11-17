import { useEffect, useId, useRef, useState } from 'react';
import type { ContentItem, Direction, Project, SourceRef } from './contracts';
import { Badge, DraftConflict, Empty, Icon, Sources, type SourceAction } from './Common';
import { useDraft, type Mutate } from './client';
import './content-production.css';

const fields = ['title', 'concept', 'hook', 'narrative', 'cta'] as const;
const fieldLabel = (field: string) => field === 'cta' ? 'Call to action' : field[0].toUpperCase() + field.slice(1);
type DirectionFields = Record<typeof fields[number], string>;
type GenerationInputs = { exploratory?: boolean; visual_only?: boolean; limitations?: string[] };
type Inspiration = { observation?: string; application?: string; sources?: SourceRef[] };
const values = (direction?: Direction): DirectionFields => ({ title: direction?.title ?? '', concept: direction?.concept ?? '', hook: direction?.hook ?? '', narrative: direction?.narrative ?? '', cta: direction?.cta ?? '' });
function InputNotes({ inputs }: { inputs: GenerationInputs }) {
  return <>{inputs.exploratory && <Badge tone="warning">Needs confirmation · exploratory</Badge>}{inputs.visual_only && <Badge tone="warning">Visual evidence only</Badge>}{!!inputs.limitations?.length && <details className="va-context-limits"><summary>Context and evidence limits</summary><ul>{inputs.limitations.map((note, index) => <li key={index}>{note}</li>)}</ul></details>}</>;
}
function DirectionCard({ project, content, direction, mutate, onSource, onProduction }: { project: Project; content: ContentItem; direction: Direction; mutate: Mutate; onSource: SourceAction; onProduction: () => void }) {
  const id = useId();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [draft, setDraft, flush, draftConflict, reloadDraft, draftVersion, adoptSaved] = useDraft(project, `direction-${content.id}-${direction.id}`, { ...values(direction), source_refs: direction.sources, base_revision: direction.revision }, mutate);
  const conflict = draft.base_revision !== direction.revision;
  const directionSources = Array.isArray(draft.source_refs) ? draft.source_refs : direction.sources;
  const dirty = fields.some(field => draft[field] !== direction[field]) || JSON.stringify(directionSources) !== JSON.stringify(direction.sources);
  const approved = direction.approved && content.approved_direction_id === direction.id && content.approved_direction_revision === direction.revision && !direction.needs_review;
  const save = async () => {
    setSaving(true);
    try {
      if (!await flush()) return;
      const saved = await mutate(`/contents/${content.id}/directions/${direction.id}/edit`, { revision: draft.base_revision, expected_editor_version: draftVersion(), fields: Object.fromEntries(fields.map(field => [field, draft[field]])), source_refs: directionSources });
      if (saved) { const revision = saved.contents.find(item => item.id === content.id)?.directions.filter(item => item.id === direction.id).at(-1)?.revision ?? direction.revision; adoptSaved(saved, { ...draft, base_revision: revision }); setEditing(false); }
    } finally { setSaving(false); }
  };
  const openProduction = async () => {
    const saved = project.active_content_id === content.id ? project : await mutate('', { active_content_id: content.id }, 'PATCH');
    if (saved) onProduction();
  };
  return <article className={`va-direction-card va-glass ${approved ? 'approved' : ''}`}>
    <DraftConflict conflict={draftConflict} reload={reloadDraft} />
    <div className="va-section-heading"><h3>{direction.title}</h3><Badge tone={direction.needs_review ? 'warning' : approved ? 'success' : ''}>{direction.needs_review ? 'Needs review' : approved ? 'Approved' : direction.approved ? 'Earlier approval' : `Draft v${direction.revision}`}</Badge></div>
    <InputNotes inputs={direction.inputs} />
    {conflict && <div className="va-notice">This editing draft belongs to an earlier revision. Your text is retained.<button type="button" onClick={() => setDraft({ ...values(direction), source_refs: direction.sources, base_revision: direction.revision })}>Use current saved revision</button></div>}
    {editing ? <form aria-label="Edit creative direction" onSubmit={event => { event.preventDefault(); void save(); }}>{fields.map(field => <div className="va-plan-field" key={field}><label htmlFor={`${id}-${field}`}>{fieldLabel(field)}</label><textarea id={`${id}-${field}`} name={field} disabled={saving} value={draft[field]} onChange={event => setDraft({ ...draft, [field]: event.target.value })} rows={field === 'narrative' ? 5 : 2} required={field === 'title' || field === 'concept'} /></div>)}{direction.sources.length > 0 && <div className="va-linked-inspiration"><input id={`${id}-sources`} type="checkbox" checked={directionSources.length > 0} disabled={saving} onChange={event => setDraft({ ...draft, source_refs: event.target.checked ? direction.sources : [] })} /><label htmlFor={`${id}-sources`}>Keep linked reference evidence</label><Sources sources={directionSources} project={project} onSource={onSource} /></div>}<div className="va-actions"><button type="button" disabled={saving} onClick={() => setEditing(false)}>Close editor</button><button className="va-primary" type="submit" disabled={conflict || draftConflict || saving}>Save direction</button></div></form> : <>
      <p className="va-direction-concept">{direction.concept}</p><dl className="va-direction-details">{[['Hook', direction.hook], ['Execution', direction.narrative], ['Call to action', direction.cta]].map(([label, value]) => value && <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <Sources sources={direction.sources} project={project} onSource={onSource} />
      {dirty && <p className="va-notice">Your saved editing draft needs a formal save before this direction can be approved.</p>}
      <div className="va-actions"><button type="button" onClick={() => setEditing(true)}>{dirty ? 'Open saved edits' : 'Edit direction'}</button>{approved ? <button type="button" className="va-primary" onClick={() => void openProduction()}>Open Production</button> : <button type="button" className="va-primary" disabled={dirty || conflict || draftConflict || direction.needs_review} onClick={() => void mutate(`/contents/${content.id}/directions/${direction.id}/approve`, { revision: direction.revision })}>Approve direction</button>}</div>
    </>}
  </article>;
}
function ManualDirection({ project, content, mutate, onClose, inspiration, inspirationRequest, onSource }: { project: Project; content: ContentItem; mutate: Mutate; onClose: () => void; inspiration?: Inspiration; inspirationRequest: number; onSource: SourceAction }) {
  const id = useId();
  const [draft, setDraft, flush, draftConflict, reloadDraft] = useDraft(project, `manual-direction-${content.id}`, { ...values(), source_refs: [] as SourceRef[] }, mutate);
  const seeded = useRef(0);
  const linkedChoices = useRef<SourceRef[]>(draft.source_refs ?? []);
  useEffect(() => {
    if (!inspiration || !inspirationRequest || seeded.current === inspirationRequest) return;
    seeded.current = inspirationRequest;
    const application = typeof inspiration.application === 'string' ? inspiration.application : '';
    const references = [...(draft.source_refs ?? []), ...(Array.isArray(inspiration.sources) ? inspiration.sources : [])];
    const seen = new Set<string>();
    const unique = references.filter(source => { const key = JSON.stringify(source); if (seen.has(key)) return false; seen.add(key); return true; });
    linkedChoices.current = unique;
    setDraft({ ...draft, concept: [draft.concept, application && !draft.concept.includes(application) ? application : ''].filter(Boolean).join('\n\n'), source_refs: unique });
  }, [inspiration, inspirationRequest, draft, setDraft]);
  const [saving, setSaving] = useState(false);
  return <form className="va-glass va-manual-direction" aria-labelledby={`${id}-heading`} onSubmit={async event => {
    event.preventDefault(); setSaving(true);
    try { if (!await flush()) return; const saved = await mutate(`/contents/${content.id}/directions`, { ...Object.fromEntries(fields.map(field => [field, draft[field]])), source_refs: draft.source_refs ?? [] }); if (saved) { setDraft({ ...values(), source_refs: [] }); onClose(); } } finally { setSaving(false); }
  }}><DraftConflict conflict={draftConflict} reload={reloadDraft} /><h3 id={`${id}-heading`}>Write a direction</h3><p className="va-muted">Describe this video's approach. Saving a direction does not approve it.</p>{fields.map(field => <div className="va-plan-field" key={field}><label htmlFor={`${id}-${field}`}>{fieldLabel(field)}</label><textarea id={`${id}-${field}`} name={field} disabled={saving} value={draft[field]} onChange={event => setDraft({ ...draft, [field]: event.target.value })} rows={field === 'concept' ? 4 : 2} required={field === 'title' || field === 'concept'} /></div>)}{linkedChoices.current.length > 0 || draft.source_refs?.length ? <div className="va-linked-inspiration"><input id={`${id}-inspiration`} type="checkbox" checked={Boolean(draft.source_refs?.length)} disabled={saving} onChange={event => setDraft({ ...draft, source_refs: event.target.checked ? linkedChoices.current : [] })} /><label htmlFor={`${id}-inspiration`}>Use linked inspiration references for this video</label><Sources sources={draft.source_refs ?? []} project={project} onSource={onSource} /><p className="va-muted">Selected evidence will be linked to this video when you save. Review it before approval.</p></div> : null}<div className="va-actions"><button type="button" disabled={saving} onClick={onClose}>Close</button><button className="va-primary" type="submit" disabled={saving || draftConflict}>Save direction</button></div></form>;
}
function VideoDirections({ project, content, mutate, onSource, onProduction, onOverview }: { project: Project; content: ContentItem; mutate: Mutate; onSource: SourceAction; onProduction: () => void; onOverview: () => void }) {
  const id = useId();
  const [manual, setManual] = useState(false);
  const [useInspiration, setUseInspiration] = useState(false);
  const [inspirationRequest, setInspirationRequest] = useState(0);
  const [visualOnly, setVisualOnly] = useState(false);
  const [startingQuestion, setStartingQuestion] = useState(false);
  const [group, setGroup] = useState(content.series_id ?? '');
  const [prompt, setPrompt] = useDraft(project, `video-instruction-${content.id}`, { instruction: '' }, mutate);
  const latest = content.directions.filter(direction => !content.directions.some(other => other.id === direction.id && other.revision > direction.revision));
  const busy = project.jobs.some(job => job.kind === 'directions' && job.content_id === content.id && ['queued', 'running'].includes(job.status));
  const hasContext = Boolean(project.briefs.at(-1)?.facts.some(fact => fact.status === 'confirmed' && fact.value.trim()));
  const selected = new Set(content.selection.resource_ids);
  const visualChoice = project.resources.some(resource => selected.has(resource.id) && ['failed', 'partial'].includes(resource.evidence.at(-1)?.coverage.speech ?? '') && resource.evidence.at(-1)?.events.some(event => ['visual', 'on_screen_text'].includes(event.kind)));
  const rawInspiration = project.editor_drafts['content-inspiration'];
  const inspiration: Inspiration | undefined = rawInspiration && typeof rawInspiration === 'object' ? rawInspiration as Inspiration : undefined;
  const generate = () => {
    const instruction = prompt.instruction.trim() || content.description.trim();
    if (!hasContext && !selected.size && !instruction) { setStartingQuestion(true); return; }
    setStartingQuestion(false); void mutate(`/contents/${content.id}/directions/generate`, { instruction, visual_only: visualOnly });
  };
  return <div className="va-plan-main">
    <div className="va-section-heading va-content-heading"><div><h2>{content.title}</h2><p className="va-muted">{project.series.find(series => series.id === content.series_id)?.title ?? 'Standalone video'} · {selected.size ? `${selected.size} references` : 'No references required'}</p>{content.description && <p>{content.description}</p>}{content.inputs && <InputNotes inputs={content.inputs} />}</div></div>
    <details className="va-video-group"><summary>Organize this video</summary><form onSubmit={event => { event.preventDefault(); void mutate(`/contents/${content.id}`, { series_id: group || null }, 'PATCH'); }}><label htmlFor={`${id}-group`}>Series</label><select id={`${id}-group`} name="series" value={group} onChange={event => setGroup(event.target.value)}><option value="">Standalone video</option>{project.series.map(series => <option value={series.id} key={series.id}>{series.title}</option>)}</select><button type="submit" disabled={group === (content.series_id ?? '')}>Move video</button></form></details>
    <details className="va-video-references"><summary>References ({selected.size})</summary><p className="va-muted">Reference use is optional and belongs to this video. Changing this scope does not start analysis.</p>{content.selection.resource_ids.length > 0 ? <ul>{content.selection.resource_ids.map(resourceId => <li key={resourceId}><span>{project.resources.find(resource => resource.id === resourceId)?.name ?? 'Unavailable reference'}</span><button type="button" className="va-link-button" aria-label={`Remove reference ${project.resources.find(resource => resource.id === resourceId)?.name ?? 'unavailable file'}`} onClick={() => void mutate('/selection', { content_id: content.id, resource_ids: content.selection.resource_ids.filter(id => id !== resourceId) })}>Remove</button></li>)}</ul> : <p>No references are linked. You can write an original direction.</p>}<div className="va-actions">{project.selection.resource_ids.length > 0 && <button type="button" onClick={() => void mutate('/selection', { content_id: content.id, resource_ids: project.selection.resource_ids })}>Use selected project references</button>}{selected.size > 0 && <button type="button" onClick={() => void mutate('/selection', { content_id: content.id, resource_ids: [] })}>Use no references</button>}</div></details>
    {inspiration?.observation && <section className="va-plan-inspiration"><h3>Reference inspiration</h3><p>{inspiration.observation}</p>{inspiration.application && <p>{inspiration.application}</p>}<Sources sources={Array.isArray(inspiration.sources) ? inspiration.sources : []} project={project} onSource={onSource} /><p className="va-muted">An optional starting point. It has not changed your direction or approved brief.</p><button type="button" onClick={() => { setUseInspiration(true); setInspirationRequest(value => value + 1); setManual(true); }}>Use as a direction draft</button></section>}
    <section className="va-glass va-video-direction-tools"><h3>Creative direction</h3><p className="va-muted">Compare different ways to make this one video, then approve the exact version you want to produce.</p><div className="va-plan-field"><label htmlFor={`${id}-instruction`}>Creative instruction for this video (optional)</label><textarea id={`${id}-instruction`} placeholder="Describe an approach, constraint, or angle to explore…" value={prompt.instruction} onChange={event => setPrompt({ instruction: event.target.value })} /></div>{visualChoice && <label className="va-visual-choice"><input type="checkbox" checked={visualOnly} onChange={event => setVisualOnly(event.target.checked)} />Continue with visual evidence only</label>}{startingQuestion && <div className="va-notice" role="status"><p>What would you like to create? Give a specific creative instruction, describe the assignment in Overview, or select references.</p><button type="button" onClick={onOverview}>Describe the assignment</button></div>}<div className="va-actions"><button type="button" onClick={() => { setUseInspiration(false); setManual(value => !value); }}>Write a direction</button><button type="button" className="va-primary" disabled={busy} onClick={generate}><Icon name="spark" />{busy ? 'Preparing directions…' : 'Generate directions'}</button></div></section>
    {manual && <ManualDirection key={content.id} project={project} content={content} mutate={mutate} onClose={() => setManual(false)} inspiration={useInspiration ? inspiration : undefined} inspirationRequest={inspirationRequest} onSource={onSource} />}
    {latest.length ? <div className="va-directions-grid">{latest.map(direction => <DirectionCard key={`${direction.id}:${direction.revision}`} project={project} content={content} direction={direction} mutate={mutate} onSource={onSource} onProduction={onProduction} />)}</div> : !manual && <Empty title="Choose how to tell this story"><p>Write your own direction or generate alternatives. References and a series are optional.</p></Empty>}
    {content.directions.length > latest.length && <details className="va-glass va-history"><summary>Earlier direction revisions</summary>{content.directions.filter(direction => !latest.includes(direction)).map(direction => <article key={`${direction.id}:${direction.revision}`}><h3>{direction.title} · v{direction.revision}</h3><p>{direction.concept}</p><p className="va-muted">Historical revision · not the current approval</p></article>)}</details>}
  </div>;
}
export default function ContentPlan({ project, mutate, onSource, onProduction, onOverview }: { project: Project; mutate: Mutate; onSource: SourceAction; onProduction: () => void; onOverview: () => void }) {
  const id = useId();
  const createDialog = useRef<HTMLDialogElement>(null);
  const topicsDialog = useRef<HTMLDialogElement>(null);
  const [creating, setCreating] = useState<'content' | 'series'>('content');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [seriesId, setSeriesId] = useState('');
  const [topicSeries, setTopicSeries] = useState('');
  const [topicVisualOnly, setTopicVisualOnly] = useState(false);
  const topicSelection = new Set(project.selection.resource_ids);
  const topicVisualChoice = project.resources.some(resource => topicSelection.has(resource.id) && ['failed', 'partial'].includes(resource.evidence.at(-1)?.coverage.speech ?? '') && resource.evidence.at(-1)?.events.some(event => ['visual', 'on_screen_text'].includes(event.kind)));
  const [topicPrompt, setTopicPrompt] = useDraft(project, 'topic-planning', { instruction: '' }, mutate);
  const [saving, setSaving] = useState(false);
  const [startingQuestion, setStartingQuestion] = useState(false);
  const content = project.contents.find(item => item.id === project.active_content_id) ?? project.contents[0];
  const busy = project.jobs.some(job => ['topics', 'concepts'].includes(job.kind) && ['queued', 'running'].includes(job.status));
  const hasContext = Boolean(project.briefs.at(-1)?.facts.some(fact => fact.status === 'confirmed' && fact.value.trim()));
  const choose = (contentId: string) => { void mutate('', { active_content_id: contentId }, 'PATCH'); };
  const openCreate = (kind: 'content' | 'series', parentSeries = '') => { setCreating(kind); setTitle(''); setDescription(''); setSeriesId(parentSeries); createDialog.current?.showModal(); };
  const create = async () => {
    if (saving) return;
    setSaving(true);
    try { const saved = await mutate(creating === 'series' ? '/series' : '/contents', creating === 'series' ? { title, concept: description } : { title, description, series_id: seriesId || null }); if (saved) createDialog.current?.close(); } finally { setSaving(false); }
  };
  const suggest = () => {
    if (!hasContext && !project.selection.resource_ids.length && !topicPrompt.instruction.trim()) { setStartingQuestion(true); return; }
    setStartingQuestion(false); void mutate('/topics/suggest', { instruction: topicPrompt.instruction, visual_only: topicVisualOnly, series_id: topicSeries || null });
  };
  return <section className="va-content-plan va-content-plan-183"><div className="va-page-heading"><div><h1>Content plan</h1><p>Plan one video, choose its direction, and prepare the shoot.</p></div><button type="button" className="va-primary" onClick={() => openCreate('content')}><Icon name="plus" />Plan a video</button></div>
    <div className="va-plan-layout"><aside className="va-content-list va-glass"><h2>Videos</h2><section><h3>Standalone</h3>{project.contents.filter(item => !item.series_id).map(item => <button type="button" key={item.id} className={content?.id === item.id ? 'active' : ''} onClick={() => choose(item.id)}><span>{item.title}</span>{item.approved_direction_id && <Icon name="check" size={15} />}</button>)}</section>{project.series.map(series => <details className="va-series-group" key={series.id} open><summary>{series.title}{series.needs_review && <Badge tone="warning">Needs review</Badge>}</summary>{series.concept && <p className="va-muted">{series.concept}</p>}{project.contents.filter(item => item.series_id === series.id).map(item => <button type="button" key={item.id} className={content?.id === item.id ? 'active' : ''} onClick={() => choose(item.id)}>{item.title}</button>)}<button type="button" className="va-link-button" onClick={() => openCreate('content', series.id)}>Add video</button></details>)}<button type="button" className="va-link-button" onClick={() => openCreate('series')}><Icon name="plus" size={16} />Create series</button><button type="button" onClick={() => topicsDialog.current?.showModal()}><Icon name="spark" size={16} />Suggest topics</button></aside>
      {content ? <VideoDirections key={content.id} project={project} content={content} mutate={mutate} onSource={onSource} onProduction={onProduction} onOverview={onOverview} /> : <Empty title="Start with one video"><p>A title is enough to start planning. Add a series only when you need one.</p><button type="button" className="va-primary" onClick={() => openCreate('content')}>Create first video</button></Empty>}
    </div>
    <dialog className="va-plan-dialog" ref={createDialog} aria-labelledby={`${id}-create-title`}><form onSubmit={event => { event.preventDefault(); void create(); }}><h2 id={`${id}-create-title`}>{creating === 'series' ? 'Create series' : 'Plan a video'}</h2><div className="va-plan-field"><label htmlFor={`${id}-title`}>Title</label><input id={`${id}-title`} name="title" autoFocus value={title} onChange={event => setTitle(event.target.value)} required maxLength={200} /></div><div className="va-plan-field"><label htmlFor={`${id}-description`}>{creating === 'series' ? 'Series concept (optional)' : 'Topic / creative starting point (optional)'}</label><textarea id={`${id}-description`} name="description" value={description} onChange={event => setDescription(event.target.value)} /></div>{creating === 'content' && <div className="va-plan-field"><label htmlFor={`${id}-series`}>Series</label><select id={`${id}-series`} name="series" value={seriesId} onChange={event => setSeriesId(event.target.value)}><option value="">Standalone video</option>{project.series.map(series => <option value={series.id} key={series.id}>{series.title}</option>)}</select></div>}<div className="va-actions"><button type="button" disabled={saving} onClick={() => createDialog.current?.close()}>Cancel</button><button type="submit" className="va-primary" disabled={saving}>{creating === 'series' ? 'Create series' : 'Create video'}</button></div></form></dialog>
    <dialog className="va-plan-dialog va-topics-dialog" ref={topicsDialog} aria-labelledby={`${id}-topics-title`}><div className="va-section-heading"><div><h2 id={`${id}-topics-title`}>Topic suggestions</h2><p className="va-muted">Preview ideas for videos. Only Add to plan creates a video.</p></div><button type="button" className="va-icon-button" aria-label="Close topic suggestions" onClick={() => topicsDialog.current?.close()}><Icon name="close" /></button></div><div className="va-plan-field"><label htmlFor={`${id}-topic-series`}>Plan topics for</label><select id={`${id}-topic-series`} value={topicSeries} onChange={event => setTopicSeries(event.target.value)}><option value="">Standalone videos</option>{project.series.map(series => <option key={series.id} value={series.id}>{series.title}</option>)}</select></div><div className="va-plan-field"><label htmlFor={`${id}-topic-instruction`}>Topic instruction (optional)</label><textarea id={`${id}-topic-instruction`} value={topicPrompt.instruction} onChange={event => setTopicPrompt({ instruction: event.target.value })} /></div>{topicVisualChoice && <label className="va-visual-choice"><input type="checkbox" checked={topicVisualOnly} onChange={event => setTopicVisualOnly(event.target.checked)} />Continue with visual evidence only</label>}{startingQuestion && <div className="va-notice" role="status"><p>Describe the task here, confirm useful context in Overview, or select references before suggesting topics.</p><button type="button" onClick={() => { topicsDialog.current?.close(); onOverview(); }}>Describe the assignment</button></div>}<button type="button" className="va-primary" disabled={busy} onClick={suggest}>{busy ? 'Preparing suggestions…' : 'Suggest topics'}</button><div className="va-topic-previews">{project.topic_suggestions?.filter(topic => (topic.series_id ?? '') === topicSeries).map(topic => <article key={topic.id}><h3>{topic.title}</h3><p>{topic.description}</p><InputNotes inputs={topic.inputs} />{topic.added_content_id ? <Badge tone="success">Added to plan</Badge> : <button type="button" onClick={() => void mutate(`/topics/${topic.id}/add`)}>Add to plan</button>}</article>)}</div></dialog>
  </section>;
}
