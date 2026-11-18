import { useEffect, useId, useRef, useState } from 'react';
import type { ContentItem, Direction, Project, SourceRef } from './contracts';
import { Badge, DraftConflict, Empty, Icon, Sources, type SourceAction } from './Common';
import { useDraft, type Mutate } from './client';
import { useDirectionReadiness } from './useDirectionReadiness';
import './content-production.css';
import './planning.css';

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
  const { readiness, readinessError, checkAgain } = useDirectionReadiness(project, content.id);
  const recordedApproval = direction.approved && content.approved_direction_id === direction.id && content.approved_direction_revision === direction.revision && !direction.needs_review;
  const inputReview = recordedApproval && readiness?.direction_current === false;
  const approved = recordedApproval && !inputReview;
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
    <div className="va-section-heading"><h3>{direction.title}</h3><Badge tone={direction.needs_review || inputReview ? 'warning' : approved ? 'success' : ''}>{direction.needs_review || inputReview ? 'Needs review' : approved ? 'Approved' : direction.approved ? 'Earlier approval' : `Draft v${direction.revision}`}</Badge></div>
    <InputNotes inputs={direction.inputs} />
    {inputReview && <p className="va-notice">{readiness?.message} Edit and save a current direction revision before approving it. Saved production remains available.</p>}
    {recordedApproval && readinessError && <p className="va-notice">{readinessError}<button type="button" onClick={checkAgain}>Check inputs again</button></p>}
    {conflict && <div className="va-notice">This editing draft belongs to an earlier revision. Your text is retained.<button type="button" onClick={() => setDraft({ ...values(direction), source_refs: direction.sources, base_revision: direction.revision })}>Use current saved revision</button></div>}
    {editing ? <form aria-label="Edit creative direction" onSubmit={event => { event.preventDefault(); void save(); }}>{fields.map(field => <div className="va-plan-field" key={field}><label htmlFor={`${id}-${field}`}>{fieldLabel(field)}</label><textarea id={`${id}-${field}`} name={field} disabled={saving} value={draft[field]} onChange={event => setDraft({ ...draft, [field]: event.target.value })} rows={field === 'narrative' ? 5 : 2} required={field === 'title' || field === 'concept'} /></div>)}{direction.sources.length > 0 && <div className="va-linked-inspiration"><input id={`${id}-sources`} type="checkbox" checked={directionSources.length > 0} disabled={saving} onChange={event => setDraft({ ...draft, source_refs: event.target.checked ? direction.sources : [] })} /><label htmlFor={`${id}-sources`}>Keep linked reference evidence</label><Sources sources={directionSources} project={project} onSource={onSource} /></div>}<div className="va-actions"><button type="button" disabled={saving} onClick={() => setEditing(false)}>Close editor</button><button className="va-primary" type="submit" disabled={conflict || draftConflict || saving}>Save direction</button></div></form> : <>
      <p className="va-direction-concept">{direction.concept}</p><dl className="va-direction-details">{[['Hook', direction.hook], ['Execution', direction.narrative], ['Call to action', direction.cta]].map(([label, value]) => value && <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
      <Sources sources={direction.sources} project={project} onSource={onSource} />
      {dirty && <p className="va-notice">Your saved editing draft needs a formal save before this direction can be approved.</p>}
      {readiness?.production_ready === false && Boolean(readiness.production_requirements?.length) && <section className="va-notice" aria-label="Before generating Production"><strong>Before generating Production</strong><ul>{readiness.production_requirements?.map((requirement, index) => <li key={index}>{requirement}</li>)}</ul><p>Review these conditions before generating a timed production plan.</p></section>}
      <div className="va-actions"><button type="button" onClick={() => setEditing(true)}>{dirty ? 'Open saved edits' : 'Edit direction'}</button>{approved ? <button type="button" className="va-primary" onClick={() => void openProduction()}>Open Production</button> : <button type="button" className="va-primary" disabled={dirty || conflict || draftConflict || direction.needs_review || inputReview} onClick={() => void mutate(`/contents/${content.id}/directions/${direction.id}/approve`, { revision: direction.revision })}>Approve direction</button>}{inputReview && project.packs.some(pack => pack.content_id === content.id) && <button type="button" onClick={() => void openProduction()}>Open saved Production</button>}</div>
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
  useEffect(() => setGroup(content.series_id ?? ''), [content.series_id]);
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
    <details className="va-video-group"><summary>Organize this video</summary><form onSubmit={event => { event.preventDefault(); void mutate(`/contents/${content.id}`, { series_id: group || null }, 'PATCH'); }}><label htmlFor={`${id}-group`}>Series</label><select id={`${id}-group`} name="series" value={group} onChange={event => setGroup(event.target.value)}><option value="">Standalone video</option>{project.series.filter(series => !series.trashed_at).map(series => <option value={series.id} key={series.id}>{series.title}</option>)}</select><button type="submit" disabled={group === (content.series_id ?? '')}>Move video</button></form></details>
    <details className="va-video-references"><summary>References ({selected.size})</summary><p className="va-muted">Reference use is optional and belongs to this video. Changing this scope does not start analysis.</p>{content.selection.resource_ids.length > 0 ? <ul>{content.selection.resource_ids.map(resourceId => <li key={resourceId}><span>{project.resources.find(resource => resource.id === resourceId)?.name ?? 'Unavailable reference'}</span><button type="button" className="va-link-button" aria-label={`Remove reference ${project.resources.find(resource => resource.id === resourceId)?.name ?? 'unavailable file'}`} onClick={() => void mutate('/selection', { content_id: content.id, resource_ids: content.selection.resource_ids.filter(id => id !== resourceId) })}>Remove</button></li>)}</ul> : <p>No references are linked. You can write an original direction.</p>}<div className="va-actions">{project.selection.resource_ids.length > 0 && <button type="button" onClick={() => void mutate('/selection', { content_id: content.id, resource_ids: project.selection.resource_ids })}>Use selected project references</button>}{selected.size > 0 && <button type="button" onClick={() => void mutate('/selection', { content_id: content.id, resource_ids: [] })}>Use no references</button>}</div></details>
    {inspiration?.observation && <section className="va-plan-inspiration"><h3>Reference inspiration</h3><p>{inspiration.observation}</p>{inspiration.application && <p>{inspiration.application}</p>}<Sources sources={Array.isArray(inspiration.sources) ? inspiration.sources : []} project={project} onSource={onSource} /><p className="va-muted">An optional starting point. It has not changed your direction or approved brief.</p><button type="button" onClick={() => { setUseInspiration(true); setInspirationRequest(value => value + 1); setManual(true); }}>Use as a direction draft</button></section>}
    <section className="va-glass va-video-direction-tools"><h3>Creative direction</h3><p className="va-muted">Compare different ways to make this one video, then approve the exact version you want to produce.</p><div className="va-plan-field"><label htmlFor={`${id}-instruction`}>Creative instruction for this video (optional)</label><textarea id={`${id}-instruction`} placeholder="Describe an approach, constraint, or angle to explore…" value={prompt.instruction} onChange={event => setPrompt({ instruction: event.target.value })} /></div>{visualChoice && <label className="va-visual-choice"><input type="checkbox" checked={visualOnly} onChange={event => setVisualOnly(event.target.checked)} />Continue with visual evidence only</label>}{startingQuestion && <div className="va-notice" role="status"><p>What would you like to create? Give a specific creative instruction, describe the assignment in Overview, or select references.</p><button type="button" onClick={onOverview}>Describe the assignment</button></div>}<div className="va-actions"><button type="button" onClick={() => { setUseInspiration(false); setManual(value => !value); }}>Write a direction</button><button type="button" className="va-primary" disabled={busy} onClick={generate}><Icon name="spark" />{busy ? 'Preparing directions…' : 'Generate directions'}</button></div></section>
    {manual && <ManualDirection key={content.id} project={project} content={content} mutate={mutate} onClose={() => setManual(false)} inspiration={useInspiration ? inspiration : undefined} inspirationRequest={inspirationRequest} onSource={onSource} />}
    {latest.length ? <div className="va-directions-grid">{latest.map(direction => <DirectionCard key={`${direction.id}:${direction.revision}`} project={project} content={content} direction={direction} mutate={mutate} onSource={onSource} onProduction={onProduction} />)}</div> : !manual && <Empty title="Choose how to tell this story"><p>Write your own direction or generate alternatives. References and a series are optional.</p></Empty>}
    {content.directions.length > latest.length && <details className="va-glass va-history"><summary>Earlier direction revisions</summary>{content.directions.filter(direction => !latest.includes(direction)).map(direction => <article key={`${direction.id}:${direction.revision}`}><h3>{direction.title} · v{direction.revision}</h3><p>{direction.concept}</p><p className="va-muted">Historical revision · not the current approval</p></article>)}</details>}
  </div>;
}
type ManageCommand = { kind: 'rename-video' | 'move-video' | 'trash-video' | 'restore-video' | 'rename-series' | 'trash-series' | 'restore-series'; id: string };
type PlanSeries = Project['series'][number];
type Action = { label: string; run: () => void; danger?: boolean };

function PlanActions({ name, actions }: { name: string; actions: Action[] }) {
  const id = useId();
  const trigger = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  return <div className="va-planning-actions">
    <button ref={trigger} type="button" className="va-planning-actions-trigger" aria-label={`Actions for ${name}`} aria-expanded={open} aria-controls={open ? id : undefined} onClick={() => setOpen(!open)}>Actions <span aria-hidden="true">{open ? '−' : '+'}</span></button>
    {open && <div id={id} className="va-planning-actions-panel" role="group" aria-label={`Actions for ${name}`} onKeyDown={event => { if (event.key === 'Escape') { event.stopPropagation(); setOpen(false); trigger.current?.focus(); } }}>{actions.map(action => <button type="button" className={action.danger ? 'va-planning-danger' : ''} key={action.label} onClick={() => { trigger.current?.focus(); setOpen(false); action.run(); }}>{action.label}</button>)}</div>}
  </div>;
}

function retainedWork(project: Project, video: ContentItem) {
  const packCount = project.packs.filter(pack => pack.content_id === video.id).length;
  return `${video.directions.length} direction revision${video.directions.length === 1 ? '' : 's'} · ${packCount} production revision${packCount === 1 ? '' : 's'}`;
}
function restoreMembers(project: Project, series: PlanSeries) {
  return project.contents.filter(video => !video.trashed_at && video.series_id === null && series.detached_contents[video.id] === video.series_assignment_version);
}

export default function ContentPlan({ project, mutate, onSource, onProduction, onOverview }: { project: Project; mutate: Mutate; onSource: SourceAction; onProduction: () => void; onOverview: () => void }) {
  const id = useId();
  const createDialog = useRef<HTMLDialogElement>(null);
  const topicsDialog = useRef<HTMLDialogElement>(null);
  const manageDialog = useRef<HTMLDialogElement>(null);
  const manageInvoker = useRef<HTMLElement | null>(null);
  const librarySummary = useRef<HTMLElement>(null);
  const [creating, setCreating] = useState<'content' | 'series'>('content');
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [seriesId, setSeriesId] = useState('');
  const [topicSeries, setTopicSeries] = useState('');
  const [topicVisualOnly, setTopicVisualOnly] = useState(false);
  const [query, setQuery] = useState('');
  const [inTrash, setInTrash] = useState(false);
  const [command, setCommand] = useState<ManageCommand | null>(null);
  const [name, setName] = useState('');
  const [destination, setDestination] = useState('');
  const [commandError, setCommandError] = useState('');
  const [notice, setNotice] = useState('');
  const [working, setWorking] = useState(false);
  const [saving, setSaving] = useState(false);
  const [createError, setCreateError] = useState('');
  const [startingQuestion, setStartingQuestion] = useState(false);
  useEffect(() => { if (command) manageDialog.current?.showModal(); }, [command]);
  const activeVideos = project.contents.filter(video => !video.trashed_at);
  const activeSeries = project.series.filter(series => !series.trashed_at);
  const trashedVideos = project.contents.filter(video => video.trashed_at);
  const trashedSeries = project.series.filter(series => series.trashed_at);
  const activeSeriesIds = new Set(activeSeries.map(series => series.id));
  const topicSelection = new Set(project.selection.resource_ids);
  const topicVisualChoice = project.resources.some(resource => topicSelection.has(resource.id) && ['failed', 'partial'].includes(resource.evidence.at(-1)?.coverage.speech ?? '') && resource.evidence.at(-1)?.events.some(event => ['visual', 'on_screen_text'].includes(event.kind)));
  const [topicPrompt, setTopicPrompt] = useDraft(project, 'topic-planning', { instruction: '' }, mutate);
  const content = activeVideos.find(item => item.id === project.active_content_id);
  const busy = project.jobs.some(job => ['topics', 'concepts'].includes(job.kind) && ['queued', 'running'].includes(job.status));
  const hasContext = Boolean(project.briefs.at(-1)?.facts.some(fact => fact.status === 'confirmed' && fact.value.trim()));
  const needle = query.trim().toLocaleLowerCase();
  const matches = (value: string) => value.toLocaleLowerCase().includes(needle);
  const matchedVideos = activeVideos.filter(video => matches(`${video.title} ${video.description}`));
  const standalone = matchedVideos.filter(video => !video.series_id || !activeSeriesIds.has(video.series_id));
  const groups = activeSeries.filter(series => matches(`${series.title} ${series.concept}`) || matchedVideos.some(video => video.series_id === series.id));
  const visibleTrashVideos = trashedVideos.filter(video => matches(`${video.title} ${video.description}`));
  const visibleTrashSeries = trashedSeries.filter(series => matches(`${series.title} ${series.concept}`));
  const affectedVideo = command?.kind.endsWith('video') ? project.contents.find(video => video.id === command.id) : undefined;
  const affectedSeries = command?.kind.endsWith('series') ? project.series.find(series => series.id === command.id) : undefined;
  const affectedMembers = affectedSeries ? activeVideos.filter(video => video.series_id === affectedSeries.id) : [];
  const restoredMembers = affectedSeries ? restoreMembers(project, affectedSeries) : [];
  const commandTitle = command?.kind === 'rename-video' ? 'Rename video' : command?.kind === 'move-video' ? 'Move video' : command?.kind === 'rename-series' ? 'Rename series' : command?.kind === 'trash-series' ? 'Move series to Trash' : command?.kind === 'restore-series' ? 'Restore series' : command?.kind === 'restore-video' ? 'Restore video' : 'Move video to Trash';
  const choose = (contentId: string) => { setInTrash(false); void mutate('', { active_content_id: contentId }, 'PATCH'); };
  const openCreate = (kind: 'content' | 'series', parentSeries = '') => { setCreating(kind); setTitle(''); setDescription(''); setSeriesId(parentSeries); setCreateError(''); createDialog.current?.showModal(); };
  const begin = (next: ManageCommand) => {
    const item = next.kind.endsWith('video') ? project.contents.find(video => video.id === next.id) : project.series.find(series => series.id === next.id);
    if (!item) return;
    manageInvoker.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setName(item.title); setDestination('series_id' in item ? item.series_id ?? '' : ''); setCommandError(''); setCommand(next);
  };
  const create = async () => {
    if (saving) return;
    setSaving(true); setCreateError('');
    let failure = '';
    try { const saved = await mutate(creating === 'series' ? '/series' : '/contents', creating === 'series' ? { title: title.trim(), concept: description } : { title: title.trim(), description, series_id: seriesId || null }, undefined, { localError: true, onError: message => { failure = message; } }); if (saved) { createDialog.current?.close(); setInTrash(false); setQuery(''); setNotice(creating === 'series' ? 'Series created. Add a video whenever you need one.' : 'Video created and selected.'); } else setCreateError(failure || 'The item was not created. Your entries are retained; review them before trying again.'); } finally { setSaving(false); }
  };
  const finish = async () => {
    if (!command || working) return;
    setWorking(true); setCommandError('');
    let failure = '';
    const options = { localError: true, onError: (message: string) => { failure = message; } };
    try {
      let saved: Project | null;
      if (command.kind === 'rename-video') saved = await mutate(`/contents/${command.id}`, { title: name.trim() }, 'PATCH', options);
      else if (command.kind === 'move-video') saved = await mutate(`/contents/${command.id}`, { series_id: destination || null }, 'PATCH', options);
      else if (command.kind === 'rename-series') saved = await mutate(`/series/${command.id}`, { title: name.trim() }, 'PATCH', options);
      else saved = await mutate(`/${command.kind.endsWith('series') ? 'series' : 'contents'}/${command.id}/${command.kind.startsWith('trash') ? 'trash' : 'restore'}`, undefined, undefined, options);
      if (saved) { setNotice(command.kind.startsWith('trash') ? `${affectedVideo?.title ?? affectedSeries?.title} moved to Trash. Saved work is retained.` : command.kind.startsWith('restore') ? `${affectedVideo?.title ?? affectedSeries?.title} restored. The selected video has not changed.` : command.kind === 'move-video' ? 'Video moved. Its identity and saved work are retained.' : 'Name updated. Saved directions and production versions are retained.'); manageDialog.current?.close(); }
      else setCommandError(failure || 'The change was not saved. Your entries are retained; review them before trying again.');
    } finally { setWorking(false); }
  };
  const suggest = () => {
    if (!hasContext && !project.selection.resource_ids.length && !topicPrompt.instruction.trim()) { setStartingQuestion(true); return; }
    setStartingQuestion(false); void mutate('/topics/suggest', { instruction: topicPrompt.instruction, visual_only: topicVisualOnly, series_id: topicSeries || null });
  };
  const videoRow = (video: ContentItem) => <li className="va-planning-item" key={video.id} data-plan-video={video.id}>
    <button type="button" className={`va-planning-select ${content?.id === video.id ? 'active' : ''}`} aria-current={content?.id === video.id ? 'true' : undefined} onClick={() => choose(video.id)}><Icon name="play" size={16} /><span>{video.title}</span>{video.approved_direction_id && <Icon name="check" size={15} />}</button>
    <PlanActions name={video.title} actions={[{ label: 'Rename video', run: () => begin({ kind: 'rename-video', id: video.id }) }, { label: video.series_id ? 'Move video / make standalone' : 'Move to a series', run: () => begin({ kind: 'move-video', id: video.id }) }, { label: 'Move video to Trash', danger: true, run: () => begin({ kind: 'trash-video', id: video.id }) }]} />
  </li>;
  return <section className="va-content-plan va-content-plan-183 va-content-plan-managed"><div className="va-page-heading"><div><h1>Content plan</h1><p>Plan one video, choose its direction, and prepare the shoot.</p></div><button type="button" className="va-primary" onClick={() => openCreate('content')}><Icon name="plus" />Plan a video</button></div>
    {notice && <p className="va-planning-notice" role="status">{notice}</p>}
    <div className="va-plan-layout"><details className="va-planning-library va-glass" open><summary ref={librarySummary}>Videos and series <span>{activeVideos.length} videos</span></summary><div className="va-planning-library-body">
      <h2>Your plan</h2>
      <search><label htmlFor={`${id}-search`}>Search videos and series</label><input id={`${id}-search`} name="plan-search" type="search" autoComplete="off" spellCheck={false} value={query} onChange={event => setQuery(event.target.value)} placeholder="Search your plan…" /></search>
      <div className="va-planning-view" role="group" aria-label="Plan view"><button type="button" aria-pressed={!inTrash} onClick={() => setInTrash(false)}>Active</button><button type="button" aria-pressed={inTrash} onClick={() => setInTrash(true)}><Icon name="trash" size={15} />Trash ({trashedVideos.length + trashedSeries.length})</button></div>
      {inTrash ? <div className="va-planning-trash-index"><p>Recover videos and series below. Browsing Trash keeps your current video selected.</p><strong>{trashedVideos.length} videos · {trashedSeries.length} series</strong></div> : <>
        <section className="va-planning-standalone"><div className="va-planning-group-heading"><h3>Standalone</h3><button type="button" className="va-link-button" onClick={() => openCreate('content')}>New video</button></div><ul className="va-planning-items">{standalone.map(videoRow)}</ul>{!standalone.length && <p className="va-planning-empty">{needle ? 'No matching standalone videos.' : 'Start with one video. A series is optional.'}</p>}</section>
        <section className="va-planning-series-list"><div className="va-planning-group-heading"><h3>Series</h3></div>{groups.map(series => { const members = activeVideos.filter(video => video.series_id === series.id); const shown = matches(`${series.title} ${series.concept}`) ? members : members.filter(video => matchedVideos.includes(video)); return <section className="va-planning-series" key={series.id} data-plan-series={series.id}><div className="va-planning-series-title"><h4>{series.title}</h4><Badge>{members.length}</Badge></div>{series.needs_review && <Badge tone="warning">Needs review</Badge>}{series.concept && <p>{series.concept}</p>}<PlanActions name={series.title} actions={[{ label: 'Add video', run: () => openCreate('content', series.id) }, { label: 'Rename series', run: () => begin({ kind: 'rename-series', id: series.id }) }, { label: 'Move series to Trash', danger: true, run: () => begin({ kind: 'trash-series', id: series.id }) }]} /><ul className="va-planning-items">{shown.map(videoRow)}</ul>{!members.length && <p className="va-planning-empty">No videos in this series yet.</p>}<button type="button" className="va-link-button" aria-label={`Add video to ${series.title}`} onClick={() => openCreate('content', series.id)}><Icon name="plus" size={15} />Add video</button></section>; })}{!groups.length && <p className="va-planning-empty">{needle ? 'No matching series.' : 'Group related videos when you need a series.'}</p>}<button type="button" onClick={() => openCreate('series')}><Icon name="plus" size={16} />Create series</button></section>
        <button type="button" className="va-planning-suggest" onClick={() => { if (!activeSeriesIds.has(topicSeries)) setTopicSeries(''); topicsDialog.current?.showModal(); }}><Icon name="spark" size={16} />Suggest topics</button>
        {needle && !standalone.length && !groups.length && <button type="button" className="va-link-button" onClick={() => setQuery('')}>Clear search</button>}
      </>}
    </div></details>
      {inTrash ? <section className="va-planning-trash va-glass"><div className="va-section-heading"><div><h2>Plan Trash</h2><p>Videos, directions, production versions and history are retained. Restore an item to continue working with it.</p></div><button type="button" onClick={() => setInTrash(false)}>Back to active plan</button></div>
        {!visibleTrashVideos.length && !visibleTrashSeries.length ? <Empty title={needle ? 'No matching items in Trash' : 'Trash is empty'}><p>{needle ? 'Try another name or clear the search.' : 'Items moved here remain recoverable. Nothing is permanently deleted.'}</p>{needle && <button type="button" onClick={() => setQuery('')}>Clear search</button>}</Empty> : <div className="va-planning-trash-cards">{visibleTrashVideos.map(video => <article key={video.id}><div><Badge>Video</Badge><h3>{video.title}</h3><p>{retainedWork(project, video)}</p></div><button type="button" aria-label={`Restore video ${video.title}`} onClick={() => begin({ kind: 'restore-video', id: video.id })}>Restore video</button></article>)}{visibleTrashSeries.map(series => <article key={series.id}><div><Badge>Series</Badge><h3>{series.title}</h3><p>{restoreMembers(project, series).length} eligible videos can rejoin. Other videos keep their current location.</p></div><button type="button" aria-label={`Restore series ${series.title}`} onClick={() => begin({ kind: 'restore-series', id: series.id })}>Restore series</button></article>)}</div>}
      </section> : content ? <VideoDirections key={content.id} project={project} content={content} mutate={mutate} onSource={onSource} onProduction={onProduction} onOverview={onOverview} /> : activeVideos.length ? <Empty title="Choose a video"><p>Select a video from your active plan to continue. Restoring a video keeps your previous selection unchanged.</p><button type="button" onClick={() => choose(activeVideos[0].id)}>Open first video</button></Empty> : <Empty title="Start with one video"><p>A title is enough to start planning. Add a series only when you need one. Saved videos in Trash can also be restored.</p><button type="button" className="va-primary" onClick={() => openCreate('content')}>Create first video</button></Empty>}
    </div>
    <dialog className="va-plan-dialog" ref={createDialog} aria-labelledby={`${id}-create-title`}><form aria-labelledby={`${id}-create-title`} onSubmit={event => { event.preventDefault(); void create(); }}><h2 id={`${id}-create-title`}>{creating === 'series' ? 'Create series' : 'Plan a video'}</h2><div className="va-plan-field"><label htmlFor={`${id}-title`}>Title</label><input id={`${id}-title`} name="title" autoFocus value={title} onChange={event => setTitle(event.target.value)} required maxLength={200} /></div><div className="va-plan-field"><label htmlFor={`${id}-description`}>{creating === 'series' ? 'Series concept (optional)' : 'Topic / creative starting point (optional)'}</label><textarea id={`${id}-description`} name="description" value={description} onChange={event => setDescription(event.target.value)} /></div>{creating === 'content' && <div className="va-plan-field"><label htmlFor={`${id}-series`}>Series</label><select id={`${id}-series`} name="series" value={seriesId} onChange={event => setSeriesId(event.target.value)}><option value="">Standalone video</option>{activeSeries.map(series => <option value={series.id} key={series.id}>{series.title}</option>)}</select></div>}{createError && <p className="va-notice" role="alert">{createError}</p>}<div className="va-actions"><button type="button" disabled={saving} onClick={() => createDialog.current?.close()}>Cancel</button><button type="submit" className="va-primary" disabled={saving}>{saving ? 'Creating…' : creating === 'series' ? 'Create series' : 'Create video'}</button></div></form></dialog>
    <dialog ref={manageDialog} className="va-plan-dialog va-planning-manage-dialog" aria-labelledby={`${id}-manage-title`} onClose={() => { setCommand(null); requestAnimationFrame(() => { if (manageInvoker.current && !manageInvoker.current.isConnected) librarySummary.current?.focus(); }); }}><form aria-labelledby={`${id}-manage-title`} onSubmit={event => { event.preventDefault(); void finish(); }}><h2 id={`${id}-manage-title`}>{commandTitle}</h2>
      {command?.kind.startsWith('rename') && <><p>Rename “{affectedVideo?.title ?? affectedSeries?.title}”. Its saved creative work stays attached to the same item.</p><div className="va-plan-field"><label htmlFor={`${id}-rename`}>Name</label><input id={`${id}-rename`} name="name" value={name} onChange={event => setName(event.target.value)} required maxLength={200} autoFocus /></div></>}
      {command?.kind === 'move-video' && <><p>Move “{affectedVideo?.title}” without creating a copy. Its directions and production history stay with this video.</p><div className="va-plan-field"><label htmlFor={`${id}-destination`}>Destination series</label><select id={`${id}-destination`} name="destination" value={destination} onChange={event => setDestination(event.target.value)} autoFocus><option value="">Standalone video</option>{activeSeries.map(series => <option key={series.id} value={series.id}>{series.title}</option>)}</select></div>{Boolean(activeSeries.find(series => series.id === destination)?.concept.trim() || activeSeries.find(series => series.id === affectedVideo?.series_id)?.concept.trim()) && <p className="va-notice">This move changes a series creative concept used by the video. Its saved work stays available and may need review before new production.</p>}</>}
      {command?.kind === 'trash-video' && <><p>Move “{affectedVideo?.title}” out of your active plan?</p>{affectedVideo && <p><strong>Kept for recovery:</strong> {retainedWork(project, affectedVideo)}. Approved directions, production sheets and historical revisions are preserved.</p>}<p>You can restore this video from Plan Trash. Nothing is permanently deleted.</p></>}
      {command?.kind === 'trash-series' && <><p>Move “{affectedSeries?.title}” to Trash and keep its {affectedMembers.length} active {affectedMembers.length === 1 ? 'video' : 'videos'} as standalone?</p>{affectedMembers.length > 0 && <ul className="va-planning-impact-list">{affectedMembers.map(video => <li key={video.id}><strong>{video.title}</strong><span>{retainedWork(project, video)}</span></li>)}</ul>}<p>Only the series is moved to Trash. These videos remain in your active plan with all saved directions, production versions and history.</p>{affectedSeries?.concept.trim() && <p className="va-notice">Leaving this series changes its shared creative context. Affected saved work may need review before new production.</p>}</>}
      {command?.kind === 'restore-video' && <><p>Restore “{affectedVideo?.title}” with all of its saved work.</p><p>{affectedVideo?.series_id && activeSeriesIds.has(affectedVideo.series_id) ? `It will return to ${activeSeries.find(series => series.id === affectedVideo.series_id)?.title}.` : 'It will return as a standalone video. Unavailable series are not restored automatically.'} Your currently selected video stays selected.</p></>}
      {command?.kind === 'restore-series' && <><p>Restore “{affectedSeries?.title}”. The {restoredMembers.length} {restoredMembers.length === 1 ? 'video below will' : 'videos below will'} rejoin this series.</p>{restoredMembers.length > 0 && <ul className="va-planning-impact-list">{restoredMembers.map(video => <li key={video.id}>{video.title}</li>)}</ul>}<p>Videos moved elsewhere, reorganized again, or independently moved to Trash keep their current state. Restoring a series does not restore trashed videos or switch your selected video.</p></>}
      {commandError && <p role="alert" className="va-notice">{commandError}</p>}
      <div className="va-actions"><button type="button" autoFocus={Boolean(command && !command.kind.startsWith('rename') && command.kind !== 'move-video')} disabled={working} onClick={() => manageDialog.current?.close()}>Cancel</button><button type="submit" className="va-primary" disabled={working}>{working ? 'Saving…' : command?.kind.startsWith('trash') ? command.kind === 'trash-series' ? 'Keep videos and trash series' : 'Move video to Trash' : command?.kind.startsWith('restore') ? 'Restore' : command?.kind === 'move-video' ? 'Move video' : 'Save name'}</button></div>
    </form></dialog>
    <dialog className="va-plan-dialog va-topics-dialog" ref={topicsDialog} aria-labelledby={`${id}-topics-title`}><div className="va-section-heading"><div><h2 id={`${id}-topics-title`}>Topic suggestions</h2><p className="va-muted">Preview ideas for videos. Only Add to plan creates a video.</p></div><button type="button" className="va-icon-button" aria-label="Close topic suggestions" onClick={() => topicsDialog.current?.close()}><Icon name="close" /></button></div><div className="va-plan-field"><label htmlFor={`${id}-topic-series`}>Plan topics for</label><select id={`${id}-topic-series`} value={topicSeries} onChange={event => setTopicSeries(event.target.value)}><option value="">Standalone videos</option>{activeSeries.map(series => <option key={series.id} value={series.id}>{series.title}</option>)}</select></div><div className="va-plan-field"><label htmlFor={`${id}-topic-instruction`}>Topic instruction (optional)</label><textarea id={`${id}-topic-instruction`} value={topicPrompt.instruction} onChange={event => setTopicPrompt({ instruction: event.target.value })} /></div>{topicVisualChoice && <label className="va-visual-choice"><input type="checkbox" checked={topicVisualOnly} onChange={event => setTopicVisualOnly(event.target.checked)} />Continue with visual evidence only</label>}{startingQuestion && <div className="va-notice" role="status"><p>Describe the task here, confirm useful context in Overview, or select references before suggesting topics.</p><button type="button" onClick={() => { topicsDialog.current?.close(); onOverview(); }}>Describe the assignment</button></div>}<button type="button" className="va-primary" disabled={busy} onClick={suggest}>{busy ? 'Preparing suggestions…' : 'Suggest topics'}</button><div className="va-topic-previews">{project.topic_suggestions?.filter(topic => (topic.series_id ?? '') === topicSeries).map(topic => <article key={topic.id}><h3>{topic.title}</h3><p>{topic.description}</p><InputNotes inputs={topic.inputs} />{topic.added_content_id ? <Badge tone="success">Added to plan</Badge> : <button type="button" onClick={() => void mutate(`/topics/${topic.id}/add`)}>Add to plan</button>}</article>)}</div></dialog>
  </section>;
}
