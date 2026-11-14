import { useState } from 'react';
import type { ProductionPack, Project } from './contracts';
import { Badge, DraftConflict, Empty, Icon, Sources, type SourceAction } from './Common';
import { useDraft, type Mutate } from './client';

const documents = [['production_brief', 'Production brief'], ['script', 'Script'], ['storyboard', 'Storyboard'], ['shot_list', 'Shot list']] as const;
type DocumentKey = typeof documents[number][0];

function PackEditor({ project, pack, historical, mutate, onSource }: { project: Project; pack: ProductionPack; historical: boolean; mutate: Mutate; onSource: SourceAction }) {
  const initial = { production_brief: pack.production_brief, script: pack.script, storyboard: pack.storyboard, shot_list: pack.shot_list, base_revision: pack.revision };
  const [draft, setDraft, flush, draftConflict, reloadDraft, draftVersion, adoptSaved] = useDraft(project, `production-${pack.id}`, initial, mutate);
  const [document, setDocument] = useState<DocumentKey>('production_brief');
  const [saving, setSaving] = useState(false);
  const conflict = !historical && draft.base_revision !== pack.revision;
  const dirty = !historical && documents.some(([key]) => draft[key] !== pack[key]);
  const save = async () => {
    setSaving(true); if (!await flush()) { setSaving(false); return; }
    const result = await mutate(`/packs/${pack.id}`, { revision: draft.base_revision, expected_editor_version: draftVersion(), ...Object.fromEntries(documents.map(([key]) => [key, draft[key]])) });
    const saved = result?.packs.filter(item => item.id === pack.id).at(-1);
    if (saved && result) adoptSaved(result, { ...draft, base_revision: saved.revision });
    setSaving(false); return saved;
  };
  const exportFile = async (format: string) => {
    const output = dirty ? await save() : pack;
    if (!output || conflict || draftConflict) return;
    const href = `/api/projects/${project.id}/packs/${output.id}/export?revision=${output.revision}&format=${format}`;
    const link = window.document.createElement('a'); link.href = href;
    if (format === 'html') { link.target = '_blank'; link.rel = 'noopener'; }
    window.document.body.append(link); link.click(); link.remove();
  };
  return <section className="va-pack va-glass"><DraftConflict conflict={draftConflict} reload={reloadDraft} /><div className="va-section-heading"><div className="va-pack-status"><Badge tone={pack.needs_review ? 'warning' : 'success'}>{pack.needs_review ? 'Inputs changed · review required' : 'Saved production pack'}</Badge><Badge>{historical ? 'Historical' : 'Current'} · v{pack.revision}</Badge>{pack.inputs.visual_only && <Badge tone="warning">Visual evidence only</Badge>}{dirty && <Badge>Unsaved to pack · draft retained</Badge>}</div><div className="va-actions"><button disabled={saving} onClick={() => void exportFile('html')}>Preview / PDF</button><details className="va-export-menu"><summary>Export production pack</summary><div><button disabled={saving} onClick={() => void exportFile('docx')}>Word document (.docx)</button><button disabled={saving} onClick={() => void exportFile('markdown')}>Markdown (.md)</button><button disabled={saving} onClick={() => void exportFile('csv')}>Shot list (.csv)</button></div></details></div></div><div className="va-tabs" role="tablist" aria-label="Production documents">{documents.map(([key, label]) => <button key={key} role="tab" aria-selected={document === key} onClick={() => setDocument(key)}>{label}</button>)}</div>
    {conflict && <div className="va-notice">This draft belongs to an earlier pack revision. Your text is retained.<button onClick={() => setDraft(initial)}>Use current saved revision</button></div>}
    {document === 'storyboard' && pack.shots.length > 0 && <div className="va-storyboard-cards">{pack.shots.map((shot, index) => <article key={shot.id}><div className="va-storyboard-frame"><span>{String(index + 1).padStart(2, '0')}</span><Icon name="production" size={34} /><p>{shot.visual}</p></div><strong>{shot.start_seconds}–{shot.end_seconds}s</strong>{shot.dialogue && <p>“{shot.dialogue}”</p>}{shot.on_screen_text && <small>Screen: {shot.on_screen_text}</small>}{shot.sound && <small>Sound: {shot.sound}</small>}</article>)}</div>}
    <label className="va-sr-only" htmlFor={`pack-${pack.id}-${document}`}>{documents.find(([key]) => key === document)?.[1]}</label><textarea id={`pack-${pack.id}-${document}`} className="va-production-document" readOnly={historical || saving} value={historical ? pack[document] : draft[document]} onChange={event => setDraft({ ...draft, [document]: event.target.value })} spellCheck />
    <div className="va-document-footer"><p className="va-muted">{historical ? 'This saved historical revision is read-only.' : 'Edits are saved as a draft. Save the pack to create a document revision.'}</p>{!historical && <button className="va-primary" disabled={!dirty || saving || conflict || draftConflict} onClick={() => void save()}>{saving ? 'Saving…' : 'Save production pack'}</button>}</div><details className="va-input-manifest"><summary>References and input versions</summary><p>Brief v{pack.inputs.brief_revision ?? '—'} · Selection v{pack.inputs.selection_revision} · Direction v{pack.inputs.direction_revision ?? '—'}</p>{pack.inputs.limitations?.map((note, index) => <p className="va-notice" key={index}>{note}</p>)}<Sources sources={pack.sources} project={project} onSource={onSource} />{Object.entries(pack.inputs.evidence_revisions).map(([id, revision]) => <p key={id}>{project.resources.find(resource => resource.id === id)?.name ?? id} · evidence v{revision}</p>)}</details>
  </section>;
}

export default function ProductionView({ project, mutate, onSource, onContent }: { project: Project; mutate: Mutate; onSource: SourceAction; onContent: () => void }) {
  const [historicalKey, setHistoricalKey] = useState('');
  const content = project.contents.find(item => item.id === project.active_content_id) ?? project.contents[0];
  const packs = project.packs.filter(pack => pack.content_id === content?.id);
  const latest = packs.at(-1);
  const selected = packs.find(pack => `${pack.id}:${pack.revision}` === historicalKey) ?? latest;
  const busy = project.jobs.some(job => job.kind === 'production' && job.content_id === content?.id && ['queued', 'running'].includes(job.status));
  return <section className="va-production"><div className="va-page-heading"><div><span className="va-eyebrow">PRODUCTION</span><h1>{content?.title ?? 'Production workspace'}</h1><p>Everything needed to prepare the shoot.</p></div>{content && <button className="va-primary" disabled={!content.approved_direction_id || busy} onClick={() => void mutate(`/contents/${content.id}/production/generate`)}><Icon name="spark" />{busy ? 'Preparing pack…' : latest ? 'Generate a new pack' : 'Generate production pack'}</button>}</div><div className="va-production-controls"><label>Video<select value={content?.id ?? ''} onChange={event => { setHistoricalKey(''); void mutate('', { active_content_id: event.target.value }, 'PATCH'); }}>{!project.contents.length && <option value="">No content yet</option>}{project.contents.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label>{packs.length > 0 && <label>Saved revision<select value={selected ? `${selected.id}:${selected.revision}` : ''} onChange={event => setHistoricalKey(event.target.value)}>{packs.slice().reverse().map(pack => <option key={`${pack.id}:${pack.revision}`} value={`${pack.id}:${pack.revision}`}>{pack === latest ? 'Latest · ' : ''}v{pack.revision} · {new Date(pack.created_at).toLocaleString()}</option>)}</select></label>}</div>{busy && <p className="va-processing" role="status"><span className="va-spinner" />Preparing the brief, script, storyboard, and shot list…</p>}{selected ? <PackEditor key={`${selected.id}:${selected.revision}`} project={project} pack={selected} historical={selected !== latest} mutate={mutate} onSource={onSource} /> : <Empty title={content?.approved_direction_id ? 'Ready to prepare a production pack' : 'Choose the direction before production'}><p>{content?.approved_direction_id ? 'Generate four editable working documents from this approved direction and its exact context.' : 'Develop and approve a creative direction in Content plan. A standalone video does not need a series.'}</p><div className="va-actions"><button onClick={onContent}>Open content plan</button>{content?.approved_direction_id && <button onClick={() => void mutate(`/contents/${content.id}/production/manual`)}>Start a blank pack</button>}</div></Empty>}</section>;
}
