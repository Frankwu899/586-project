import { useId, useState } from 'react';
import type { ProductionPack, ProductionShot, Project, SourceRef } from './contracts';
import { Badge, DraftConflict, Empty, Icon, Sources, type SourceAction } from './Common';
import { useDraft, type Mutate } from './client';
import './content-production.css';

const documents = [['production_brief', 'Production brief'], ['script', 'Script'], ['storyboard', 'Storyboard'], ['shot_list', 'Shot list']] as const;
type DocumentKey = typeof documents[number][0];
const shotFields = [['framing_camera', 'Framing / Camera'], ['visual', 'Visual / Action'], ['dialogue', 'Dialogue / VO'], ['on_screen_text', 'On-screen Text'], ['sound', 'Music / SFX'], ['notes', 'Production Notes']] as const;
type ShotText = typeof shotFields[number][0];
const number = (index: number) => String(index + 1).padStart(2, '0');
const sourceKey = (source: SourceRef) => [source.resource_id, source.evidence_revision, source.event_id, source.start_seconds, source.end_seconds].join(':');
const seconds = (value: number) => `${Math.floor(value / 60).toString().padStart(2, '0')}:${(value % 60).toFixed(value % 1 ? 2 : 0).padStart(2, '0')}`;
function inputSources(project: Project, pack: ProductionPack) {
  const candidates = [...pack.sources, ...project.contents.flatMap(content => content.directions.flatMap(direction => direction.sources)), ...project.analyses.flatMap(analysis => [...analysis.sources, ...(analysis.key_insights ?? []).flatMap(insight => insight.sources)])];
  const seen = new Set<string>();
  return candidates.filter(source => {
    if (!source.resource_id || source.evidence_revision !== pack.inputs.evidence_revisions[source.resource_id]) return false;
    const key = sourceKey(source); if (seen.has(key)) return false; seen.add(key); return true;
  });
}
function Inputs({ project, pack, onSource }: { project: Project; pack: ProductionPack; onSource: SourceAction }) {
  return <details className="va-input-manifest"><summary>References and input versions</summary><p>Brief v{pack.inputs.brief_revision ?? '—'} · Selection v{pack.inputs.selection_revision} · Direction v{pack.inputs.direction_revision ?? '—'}</p>{pack.inputs.limitations?.map((note, index) => <p className="va-notice" key={index}>{note}</p>)}<Sources sources={pack.sources} project={project} onSource={onSource} /></details>;
}
function download(project: Project, pack: ProductionPack, format: string) {
  const link = document.createElement('a');
  link.href = `/api/projects/${encodeURIComponent(project.id)}/packs/${encodeURIComponent(pack.id)}/export?revision=${pack.revision}&format=${format}`;
  if (format === 'html') { link.target = '_blank'; link.rel = 'noopener'; }
  document.body.append(link); link.click(); link.remove();
}
function LegacyPackEditor({ project, pack, historical, mutate, onSource }: { project: Project; pack: ProductionPack; historical: boolean; mutate: Mutate; onSource: SourceAction }) {
  const initial = { production_brief: pack.production_brief, script: pack.script, storyboard: pack.storyboard, shot_list: pack.shot_list, base_revision: pack.revision };
  const [draft, setDraft, flush, draftConflict, reloadDraft, draftVersion, adoptSaved] = useDraft(project, `production-${pack.id}`, initial, mutate);
  const [document, setDocument] = useState<DocumentKey>('production_brief');
  const [saving, setSaving] = useState(false);
  const conflict = !historical && draft.base_revision !== pack.revision;
  const dirty = !historical && documents.some(([key]) => draft[key] !== pack[key]);
  const save = async () => {
    setSaving(true);
    try {
      if (!await flush()) return null;
      const result = await mutate(`/packs/${pack.id}`, { revision: draft.base_revision, expected_editor_version: draftVersion(), ...Object.fromEntries(documents.map(([key]) => [key, draft[key]])) });
      const saved = result?.packs.filter(item => item.id === pack.id).at(-1);
      if (saved && result) adoptSaved(result, { ...draft, base_revision: saved.revision });
      return saved;
    } finally { setSaving(false); }
  };
  const exportFile = async (format: string) => { const saved = dirty ? await save() : pack; if (saved && !conflict && !draftConflict) download(project, saved, format); };
  return <section className="va-pack va-glass va-legacy-pack"><div className="va-section-heading"><div><h2>Legacy production documents</h2><p className="va-muted">This saved version has no synchronized editable sheet. Its original documents remain available; no shot rows have been invented.</p></div><Badge>{historical ? 'Historical' : 'Current'} · v{pack.revision}</Badge></div><DraftConflict conflict={draftConflict} reload={reloadDraft} /><div className="va-tabs" role="tablist" aria-label="Legacy production documents">{documents.map(([key, label]) => <button type="button" key={key} role="tab" aria-selected={document === key} onClick={() => setDocument(key)}>{label}</button>)}</div>{conflict && <div className="va-notice">Your draft belongs to an earlier version. Its text is retained.<button type="button" onClick={() => setDraft(initial)}>Use current saved revision</button></div>}<label className="va-sr-only" htmlFor={`legacy-${pack.id}-${document}`}>{documents.find(([key]) => key === document)?.[1]}</label><textarea id={`legacy-${pack.id}-${document}`} className="va-production-document" readOnly={historical || saving} value={historical ? pack[document] : draft[document]} onChange={event => setDraft({ ...draft, [document]: event.target.value })} /><div className="va-document-footer"><p className="va-muted">{historical ? 'Read-only historical version.' : 'Save edited legacy documents as a new version.'}</p>{!historical && <button type="button" className="va-primary" disabled={!dirty || saving || conflict || draftConflict} onClick={() => void save()}>Save legacy documents</button>}</div><details className="va-export-menu"><summary>Export legacy documents</summary><div>{[['csv', 'Original CSV'], ['markdown', 'Markdown (.md)'], ['docx', 'Word document (.docx)'], ['html', 'Preview / PDF']].map(([format, label]) => <button type="button" key={format} disabled={saving} onClick={() => void exportFile(format)}>{label}</button>)}</div></details><Inputs project={project} pack={pack} onSource={onSource} /></section>;
}
function SheetEditor({ project, pack, historical, mutate, onSource, converting = false }: { project: Project; pack: ProductionPack; historical: boolean; mutate: Mutate; onSource: SourceAction; converting?: boolean }) {
  const id = useId();
  const [draft, setDraft, flush, draftConflict, reloadDraft, draftVersion, adoptSaved] = useDraft(project, `production-${pack.id}`, { production_brief: pack.production_brief, shots: pack.shots, base_revision: pack.revision }, mutate);
  const [saving, setSaving] = useState(false);
  const shots = historical ? pack.shots : Array.isArray(draft.shots) ? draft.shots : pack.shots;
  const brief = historical ? pack.production_brief : draft.production_brief;
  const conflict = !historical && draft.base_revision !== pack.revision;
  const dirty = !historical && (converting || brief !== pack.production_brief || JSON.stringify(shots) !== JSON.stringify(pack.shots));
  const refs = inputSources(project, pack);
  const replace = (index: number, changes: Partial<ProductionShot>) => setDraft({ ...draft, shots: shots.map((shot, i) => i === index ? { ...shot, ...changes } : shot) });
  const add = () => { const start = shots.at(-1)?.end_seconds ?? 0; setDraft({ ...draft, shots: [...shots, { id: `shot_${crypto.randomUUID().replaceAll('-', '')}`, start_seconds: start, end_seconds: start + 1, framing_camera: '', visual: '', dialogue: '', on_screen_text: '', sound: '', notes: '', sources: [] }] }); };
  const remove = (index: number) => {
    const removed = shots[index]; const duration = removed.end_seconds - removed.start_seconds;
    setDraft({ ...draft, shots: shots.filter((_, i) => i !== index).map((shot, i) => i >= index ? { ...shot, start_seconds: Math.max(0, shot.start_seconds - duration), end_seconds: Math.max(0, shot.end_seconds - duration) } : shot) });
  };
  const save = async () => {
    if (historical || saving) return null;
    setSaving(true);
    try {
      if (!await flush()) return null;
      const result = await mutate(`/packs/${pack.id}`, { revision: draft.base_revision, expected_editor_version: draftVersion(), production_brief: brief, shots, sheet_format: 'storyboard_sheet' });
      const saved = result?.packs.filter(item => item.id === pack.id).at(-1);
      if (saved && result) adoptSaved(result, { production_brief: saved.production_brief, shots: saved.shots, base_revision: saved.revision });
      return saved;
    } finally { setSaving(false); }
  };
  const exportFile = async (format: string) => { if (conflict || draftConflict) return; const saved = dirty ? await save() : pack; if (saved) download(project, saved, format); };
  return <section className="va-production-sheet" aria-label="Production brief and storyboard sheet"><DraftConflict conflict={draftConflict} reload={reloadDraft} /><div className="va-sheet-toolbar"><div className="va-pack-status"><Badge tone={pack.needs_review ? 'warning' : 'success'}>{pack.needs_review ? 'Inputs changed · review' : 'Saved locally'}</Badge><Badge>{historical ? 'Historical' : 'Current'} · v{pack.revision}</Badge>{pack.inputs.visual_only && <Badge tone="warning">Visual evidence only</Badge>}{dirty && <Badge>Draft retained · save to update</Badge>}</div><div className="va-actions">{!historical && <button type="button" disabled={!dirty || saving || conflict || draftConflict} onClick={() => void save()}>{saving ? 'Saving…' : 'Save sheet'}</button>}<button type="button" className="va-primary" disabled={saving || conflict || draftConflict} onClick={() => void exportFile('csv')}><Icon name="upload" size={17} />Export sheet</button><details className="va-export-menu"><summary>Other exports</summary><div>{[['markdown', 'Markdown (.md)'], ['docx', 'Word document (.docx)'], ['html', 'Preview / PDF']].map(([format, label]) => <button type="button" key={format} disabled={saving} onClick={() => void exportFile(format)}>{label}</button>)}</div></details></div></div>
    {conflict && <div className="va-notice">A newer sheet version is saved. Your local changes are retained.<button type="button" onClick={() => setDraft({ production_brief: pack.production_brief, shots: pack.shots, base_revision: pack.revision })}>Use current saved revision</button></div>}
    <section className="va-sheet-brief va-glass"><label htmlFor={`${id}-brief`}>Production brief</label><textarea id={`${id}-brief`} value={brief} readOnly={historical || saving} onChange={event => setDraft({ ...draft, production_brief: event.target.value })} placeholder="Goal, audience, platform, duration, execution constraints, and permitted claims." rows={3} /></section>
    <div className="va-section-heading"><div><h2 id={`${id}-sheet-title`}>Storyboard sheet</h2><p className="va-muted">One row per planned shot. Timecode is the new video's planned time, separate from reference evidence.</p></div>{!historical && <button type="button" disabled={saving} onClick={add}><Icon name="plus" size={17} />Add shot</button>}</div>
    {shots.length ? <><div className="va-sheet-scroll" role="region" aria-labelledby={`${id}-sheet-title`} tabIndex={0}><table className="va-storyboard-sheet"><colgroup>{[6, 11, 11, 20, 18, 12, 9, 13].map((width, index) => <col key={index} style={{ width: `${width}%` }} />)}</colgroup><thead><tr>{['Shot', 'Timecode', ...shotFields.map(([, label]) => label)].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{shots.map((shot, index) => <tr key={shot.id}><th scope="row"><span>{number(index)}</span>{!historical && <button type="button" className="va-link-button" disabled={saving} aria-label={`Remove shot ${number(index)}`} onClick={() => remove(index)}>Remove</button>}</th><td><div className="va-shot-time"><strong className="va-shot-time-range">{seconds(shot.start_seconds)}–{seconds(shot.end_seconds)}</strong><label htmlFor={`${id}-${shot.id}-start`}>Start (s)</label><input id={`${id}-${shot.id}-start`} aria-label={`Shot ${number(index)} Start (seconds)`} type="number" min="0" step="0.1" value={shot.start_seconds} readOnly={historical || saving} onChange={event => replace(index, { start_seconds: Number(event.target.value) })} /><label htmlFor={`${id}-${shot.id}-end`}>End (s)</label><input id={`${id}-${shot.id}-end`} aria-label={`Shot ${number(index)} End (seconds)`} type="number" min="0.1" step="0.1" value={shot.end_seconds} readOnly={historical || saving} onChange={event => replace(index, { end_seconds: Number(event.target.value) })} /></div></td>{shotFields.map(([key, label]) => <td key={key}><label className="va-sr-only" htmlFor={`${id}-${shot.id}-${key}`}>Shot {number(index)} {label}</label><textarea id={`${id}-${shot.id}-${key}`} value={shot[key]} readOnly={historical || saving} onChange={event => replace(index, { [key]: event.target.value } as Pick<ProductionShot, ShotText>)} rows={key === 'visual' || key === 'dialogue' ? 4 : 3} />{key === 'notes' && <><Sources sources={shot.sources} project={project} onSource={onSource} />{!historical && <details className="va-shot-reference"><summary>Reference link</summary><label className="va-sr-only" htmlFor={`${id}-${shot.id}-reference`}>Shot {number(index)} reference</label><select id={`${id}-${shot.id}-reference`} value={shot.sources[0] ? sourceKey(shot.sources[0]) : ''} onChange={event => { const source = refs.find(source => sourceKey(source) === event.target.value); replace(index, { sources: source ? [source] : [] }); }}><option value="">No reference</option>{shot.sources[0] && !refs.some(source => sourceKey(source) === sourceKey(shot.sources[0])) && <option value={sourceKey(shot.sources[0])}>Saved historical reference</option>}{refs.map(source => <option key={sourceKey(source)} value={sourceKey(source)}>{project.resources.find(resource => resource.id === source.resource_id)?.name ?? 'Source'} · {source.start_seconds == null ? 'Saved evidence' : `${source.start_seconds}–${source.end_seconds}s`}</option>)}</select>{!refs.length && <p className="va-muted">No saved evidence links are available for this input revision.</p>}</details>}</>}</td>)}</tr>)}</tbody></table></div><details className="va-sheet-reader"><summary>Read shot by shot</summary>{shots.map((shot, index) => <article key={shot.id}><h3>Shot {number(index)} · {seconds(shot.start_seconds)}–{seconds(shot.end_seconds)}</h3><dl>{shotFields.map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{shot[key] || '—'}</dd></div>)}</dl><Sources sources={shot.sources} project={project} onSource={onSource} /></article>)}</details></> : <div className="va-brief-empty">This sheet is empty. {historical ? 'This historical version has no shot rows.' : 'Add a shot to start your own plan; no rows are inferred from old documents.'}</div>}
    <Inputs project={project} pack={pack} onSource={onSource} />
  </section>;
}
export default function ProductionView({ project, mutate, onSource, onContent }: { project: Project; mutate: Mutate; onSource: SourceAction; onContent: () => void }) {
  const [historicalKey, setHistoricalKey] = useState('');
  const [converting, setConverting] = useState('');
  const content = project.contents.find(item => item.id === project.active_content_id) ?? project.contents[0];
  const packs = project.packs.filter(pack => pack.content_id === content?.id);
  const latest = packs.at(-1);
  const selected = packs.find(pack => `${pack.id}:${pack.revision}` === historicalKey) ?? latest;
  const direction = content?.directions.find(direction => direction.id === content.approved_direction_id && direction.revision === content.approved_direction_revision);
  const approved = Boolean(direction?.approved && !direction.needs_review);
  const busy = project.jobs.some(job => job.kind === 'production' && job.content_id === content?.id && ['queued', 'running'].includes(job.status));
  const sheet = selected?.sheet_format === 'storyboard_sheet' || (selected && converting === `${selected.id}:${selected.revision}`);
  return <section className="va-production va-production-183"><div className="va-page-heading"><div><span className="va-eyebrow">PRODUCTION</span><h1>{content?.title ?? 'Production workspace'}</h1><p>{approved ? `Approved direction: ${direction?.title}` : 'Choose and approve a direction for this video.'}</p></div>{content && approved && <button type="button" disabled={busy} onClick={() => void mutate(`/contents/${content.id}/production/generate`)}><Icon name="spark" />{busy ? 'Preparing sheet…' : latest ? 'Generate a new sheet' : 'Generate storyboard sheet'}</button>}</div>
    <div className="va-production-controls"><label htmlFor={`production-video-${project.id}`}>Video</label><select id={`production-video-${project.id}`} value={content?.id ?? ''} onChange={event => { setHistoricalKey(''); setConverting(''); void mutate('', { active_content_id: event.target.value }, 'PATCH'); }}>{!project.contents.length && <option value="">No video yet</option>}{project.contents.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select>{packs.length > 0 && <><label htmlFor={`production-revision-${project.id}`}>Saved revision</label><select id={`production-revision-${project.id}`} value={selected ? `${selected.id}:${selected.revision}` : ''} onChange={event => { setHistoricalKey(event.target.value); setConverting(''); }}>{packs.slice().reverse().map(pack => <option key={`${pack.id}:${pack.revision}`} value={`${pack.id}:${pack.revision}`}>{pack === latest ? 'Latest · ' : ''}v{pack.revision} · {new Date(pack.created_at).toLocaleString()}</option>)}</select></>}</div>
    {busy && <p className="va-processing" role="status"><span className="va-spinner" />Preparing the brief and storyboard sheet. Earlier saved work remains available.</p>}
    {content && !approved && <div className="va-notice">Saved production versions remain available. Review the current direction before starting new production.<button type="button" onClick={onContent}>Review direction</button></div>}
    {selected ? sheet ? <SheetEditor key={`${selected.id}:${selected.revision}:sheet`} project={project} pack={selected} historical={selected !== latest} converting={selected.sheet_format !== 'storyboard_sheet'} mutate={mutate} onSource={onSource} /> : <><LegacyPackEditor key={`${selected.id}:${selected.revision}:legacy`} project={project} pack={selected} historical={selected !== latest} mutate={mutate} onSource={onSource} />{selected === latest && <div className="va-legacy-conversion">{selected.shots.length > 0 && <button type="button" onClick={() => setConverting(`${selected.id}:${selected.revision}`)}>Edit saved shots as a sheet</button>}{approved && <button type="button" onClick={() => void mutate(`/contents/${content!.id}/production/manual`)}>Start a new blank sheet</button>}<p className="va-muted">Legacy versions stay intact. Existing structured shots can become a new sheet revision; free text is never guessed into rows.</p></div>}</> : <Empty title={approved ? 'Ready to plan the shoot' : content ? 'Review a direction before production' : 'Plan a video first'}><p>{approved ? 'Generate a timed sheet from your confirmed inputs, or start a blank sheet and write your own shots.' : 'A standalone video needs no series or reference. Choose one exact direction in Content plan.'}</p><div className="va-actions">{approved ? <button type="button" className="va-primary" onClick={() => void mutate(`/contents/${content!.id}/production/manual`)}>Start a blank sheet</button> : <button type="button" className="va-primary" onClick={onContent}>{content ? 'Review direction' : 'Plan a video'}</button>}</div></Empty>}
  </section>;
}
