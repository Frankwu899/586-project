import { useRef, useState } from 'react';
import type { EvidenceEvent, ExtractedBlock, Project, Resource, SourceRef } from './contracts';
import { Badge, FailureNotice, DraftConflict } from './Common';
import { fileUrl, useDraft, type Mutate } from './client';
import { resourceMessage, failureMessage } from './status';
import { resourceIsTrashed } from './resourceLibrary';

export function EvidenceEditor({ project, resource, mutate, onClose }: { project: Project; resource: Resource; mutate: Mutate; onClose: () => void }) {
  const evidence = resource.evidence.at(-1)!;
  const [draft, setDraft, flush, conflict, reload, draftVersion, adoptSaved] = useDraft(project, `evidence-${resource.id}`, { events: evidence.events, base_revision: evidence.revision }, mutate);
  const [applying, setApplying] = useState(false);
  const apply = async () => {
    setApplying(true);
    if (!await flush()) { setApplying(false); return; }
    const saved = await mutate(`/resources/${resource.id}/evidence`, { events: draft.events, reviewed: false, base_revision: draft.base_revision, expected_editor_version: draftVersion() });
    if (saved) {
      const corrected = saved.resources.find(item => item.id === resource.id)?.evidence.at(-1);
      adoptSaved(saved, { events: corrected?.events ?? draft.events, base_revision: corrected?.revision ?? evidence.revision });
      onClose();
    }
    setApplying(false);
  };
  const edit = (id: string, changes: Partial<EvidenceEvent>) => setDraft({ ...draft, events: draft.events.map(event => event.id === id ? { ...event, ...changes } : event) });
  return <section className="va-evidence-editor"><DraftConflict conflict={conflict} reload={reload} /><div className="va-section-heading"><h3>Correct evidence</h3><button disabled={applying} onClick={onClose}>Close</button></div><p className="va-muted">Original recognition is preserved. Applying corrections creates a new evidence revision.</p>{draft.events.map(event => <div className="va-evidence-edit" key={event.id}><Badge>{event.kind.replaceAll('_', ' ')}</Badge><textarea disabled={applying} aria-label={`${event.kind} text`} value={event.text} onChange={change => edit(event.id, { text: change.target.value })} /><div className="va-time-inputs"><label>Start (seconds)<input type="number" disabled={applying} min="0" step="0.01" value={event.start_seconds} onChange={change => edit(event.id, { start_seconds: Number(change.target.value) })} /></label><label>End (seconds)<input type="number" disabled={applying} min="0" step="0.01" value={event.end_seconds} onChange={change => edit(event.id, { end_seconds: Number(change.target.value) })} /></label></div></div>)}<button className="va-primary" disabled={applying || conflict} onClick={() => void apply()}>Apply corrections</button></section>;
}

export function DocumentEditor({ project, resource, mutate, onClose }: { project: Project; resource: Resource; mutate: Mutate; onClose: () => void }) {
  const [draft, setDraft, flush, conflict, reload, draftVersion, adoptSaved] = useDraft(project, `blocks-${resource.id}`, { blocks: resource.blocks, base_revision: resource.extraction_revision }, mutate);
  const [applying, setApplying] = useState(false);
  const apply = async () => {
    setApplying(true);
    if (!await flush()) { setApplying(false); return; }
    const saved = await mutate(`/resources/${resource.id}/blocks`, { blocks: draft.blocks, base_revision: draft.base_revision, expected_editor_version: draftVersion() });
    if (saved) {
      const corrected = saved.resources.find(item => item.id === resource.id);
      adoptSaved(saved, { blocks: corrected?.blocks ?? draft.blocks, base_revision: corrected?.extraction_revision ?? draft.base_revision });
      onClose();
    }
    setApplying(false);
  };
  return <section className="va-document-editor"><DraftConflict conflict={conflict} reload={reload} /><div className="va-section-heading"><h3>Correct extraction</h3><button disabled={applying} onClick={onClose}>Close</button></div>{draft.blocks.map(block => <label key={block.id}>{block.locator}<textarea disabled={applying} value={block.text} onChange={event => setDraft({ ...draft, blocks: draft.blocks.map(item => item.id === block.id ? { ...item, text: event.target.value } : item) })} /></label>)}<button className="va-primary" disabled={applying || conflict} onClick={() => void apply()}>Apply corrections</button></section>;
}

export default function ResourceInspector({ project, resource, source, mutate }: { project: Project; resource: Resource; source: SourceRef | null; mutate: Mutate }) {
  const [editing, setEditing] = useState(false);
  const [latest, setLatest] = useState(false);
  const [working, setWorking] = useState(false);
  const relink = useRef<HTMLInputElement>(null);
  const cited = source?.extraction_revision;
  const old = cited != null && cited !== resource.extraction_revision ? resource.extraction_history.find(item => item.revision === cited) : undefined;
  const missing = !latest && cited != null && cited !== resource.extraction_revision && !old;
  const blocks = missing ? [] : !latest && old && Array.isArray(old.blocks) ? old.blocks as unknown as ExtractedBlock[] : resource.blocks;
  const historical = !latest && Boolean(old);
  const trashed = resourceIsTrashed(project, resource);
  return <section className="va-resource-inspector va-glass" aria-label="File review"><div className="va-section-heading"><h2>{resource.name}</h2><Badge>{trashed ? 'In Trash' : resourceMessage(resource)}</Badge></div>
    {missing && <div className="va-notice" role="alert">Requested extraction revision {cited} is unavailable. No current text was substituted.<button type="button" onClick={() => setLatest(true)}>View current extraction</button></div>}
    {historical && <p className="va-notice">Showing the exact historical extraction cited by this output.<button type="button" onClick={() => setLatest(true)}>View current extraction</button></p>}
    {resource.kind === 'image' && !trashed && <img className="va-resource-image" src={fileUrl(project.id, resource.id)} alt={resource.name} />}
    {resource.error && <FailureNotice message={resource.error} />}
    {editing ? <DocumentEditor project={project} resource={resource} mutate={mutate} onClose={() => setEditing(false)} /> : <div className="va-document-blocks">{blocks.map(block => <article key={block.id}><small>{block.locator}</small><p>{block.text}</p></article>)}{!blocks.length && !missing && <p className="va-muted">{resource.status === 'processing' || resource.status === 'stored' ? 'Extracting the document…' : 'No readable text was extracted. The original file is preserved; paste useful text in Overview if needed.'}</p>}</div>}
    {resource.warnings.length > 0 && <details><summary>Extraction limits</summary>{resource.warnings.map((warning, index) => <p key={index}>{failureMessage(warning)}</p>)}</details>}
    <div className="va-inspector-actions">{blocks.length > 0 && !historical && !missing && <button type="button" disabled={trashed} onClick={() => setEditing(true)}>Correct extraction</button>}<button type="button" disabled={working || trashed} onClick={async () => { setWorking(true); try { await mutate(`/resources/${resource.id}/extract`); } finally { setWorking(false); } }}>{working ? 'Preparing…' : 'Retry extraction'}</button><a className="va-button-link" href={fileUrl(project.id, resource.id)} target="_blank" rel="noreferrer">Open original</a><input ref={relink} className="va-sr-only" tabIndex={-1} type="file" onChange={async event => { const file = event.target.files?.[0]; if (!file) return; const body = new FormData(); body.append('file', file); await mutate(`/resources/${resource.id}/relink`, body); }} /><button type="button" disabled={trashed} onClick={() => relink.current?.click()}>Relink original</button></div>
  </section>;
}
