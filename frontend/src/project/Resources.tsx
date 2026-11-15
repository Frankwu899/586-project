import { useEffect, useRef, useState } from 'react';
import type { EvidenceEvent, ExtractedBlock, Project, Resource, SourceRef } from './contracts';
import { Badge, FailureNotice, SupportDetails, DraftConflict, Empty, Icon, time } from './Common';
import { fileUrl, useDraft, type Mutate } from './client';
import { playbackSeconds } from './sourceTiming';
import { channelLabel, coverageMessage, resourceMessage, failureMessage, evidenceOrigin } from './status';

function EvidenceEditor({ project, resource, mutate, onClose }: { project: Project; resource: Resource; mutate: Mutate; onClose: () => void }) {
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

function DocumentEditor({ project, resource, mutate, onClose }: { project: Project; resource: Resource; mutate: Mutate; onClose: () => void }) {
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

function Inspector({ project, resource, source, mutate }: { project: Project; resource: Resource; source: SourceRef | null; mutate: Mutate }) {
  const player = useRef<HTMLVideoElement | HTMLAudioElement>(null);
  const [tab, setTab] = useState('speech');
  const [editing, setEditing] = useState(false);
  const [editingDocument, setEditingDocument] = useState(false);
  const [playbackError, setPlaybackError] = useState('');
  const relink = useRef<HTMLInputElement>(null);
  const latestEvidence = resource.evidence.at(-1);
  const activeResourceJobs = project.jobs.filter(job => job.resource_id === resource.id && ['queued', 'running'].includes(job.status));
  const recognizing = activeResourceJobs.some(job => ['reference_extraction', 'recognize'].includes(job.kind));
  const preparing = activeResourceJobs.some(job => job.kind === 'extract');
  const [startingRecognition, setStartingRecognition] = useState(false);
  const [startingPreparation, setStartingPreparation] = useState(false);
  const retryRecognition = async () => {
    if (recognizing || preparing || startingRecognition || startingPreparation) return;
    setStartingRecognition(true);
    try { await mutate(`/resources/${resource.id}/recognize`); } finally { setStartingRecognition(false); }
  };
  const prepare = async () => {
    if (recognizing || preparing || startingRecognition || startingPreparation) return;
    setStartingPreparation(true);
    try { await mutate(`/resources/${resource.id}/extract`); } finally { setStartingPreparation(false); }
  };
  const [showLatest, setShowLatest] = useState(false);
  const citedEvidence = source?.resource_id === resource.id && source.evidence_revision != null ? resource.evidence.find(item => item.revision === source.evidence_revision) : undefined;
  const evidence = showLatest ? latestEvidence : citedEvidence ?? latestEvidence;
  const historicalEvidence = evidence !== latestEvidence;
  const speechDetails = (evidence?.support_details ?? []).filter(record => ['transcription_chunk', 'saved_evidence_reuse'].includes(record.stage));
  const origin = evidenceOrigin(speechDetails);
  const latestJob = project.jobs.filter(job => job.resource_id === resource.id).at(-1);
  const failureJob = !historicalEvidence && latestJob && ['failed', 'partial'].includes(latestJob.status) ? latestJob : undefined;
  const support = [{ ...evidence?.diagnostics, ...failureJob?.diagnostics, project_id: project.id, resource_id: resource.id, evidence_revision: evidence?.revision ?? '', job_id: failureJob?.id ?? '' }, ...(failureJob?.support_details?.length ? failureJob.support_details : evidence?.support_details ?? [])];
  const needsSpeech = ['failed', 'partial'].includes(latestEvidence?.coverage.speech ?? '') || latestEvidence?.diagnostics?.speech === 'speech_merge_conflict';
  const citedExtraction = source?.resource_id === resource.id && source.extraction_revision != null && source.extraction_revision !== resource.extraction_revision ? resource.extraction_history.find(item => item.revision === source.extraction_revision) : undefined;
  const documentBlocks = !showLatest && citedExtraction && Array.isArray(citedExtraction.blocks) ? citedExtraction.blocks as unknown as ExtractedBlock[] : resource.blocks;
  useEffect(() => setShowLatest(false), [source]);
  const citationTime = source?.resource_id === resource.id && source.start_seconds != null ? playbackSeconds(resource, source.start_seconds) : null;
  useEffect(() => { if (citationTime != null && player.current) player.current.currentTime = citationTime; }, [source, citationTime]);
  const seek = (seconds: number) => { if (player.current) player.current.currentTime = playbackSeconds(resource, seconds); };
  return <aside className="va-resource-inspector va-glass"><div className="va-section-heading"><h2>{resource.name}</h2><Badge tone={['failed', 'missing', 'partial'].includes(resource.status) || Object.values(evidence?.coverage ?? {}).some(value => ['failed', 'partial', 'error'].includes(value)) ? 'warning' : ''}>{resourceMessage(resource)}</Badge></div>
    {resource.kind === 'video' && <video ref={player as React.RefObject<HTMLVideoElement>} src={fileUrl(project.id, resource.id, 'playback')} controls preload="metadata" onLoadedMetadata={() => { setPlaybackError(''); if (source?.resource_id === resource.id && source.start_seconds != null) seek(source.start_seconds); }} onError={() => setPlaybackError('Playback is unavailable. The original and saved evidence are retained. Check the processing status or relink the original file.')} />}
    {resource.kind === 'audio' && <audio ref={player as React.RefObject<HTMLAudioElement>} src={fileUrl(project.id, resource.id, 'playback')} controls preload="metadata" onLoadedMetadata={() => { if (source?.resource_id === resource.id && source.start_seconds != null) seek(source.start_seconds); }} onError={() => setPlaybackError('Audio playback is unavailable. Check the source file and processing status.')} />}
    {resource.kind === 'image' && <img className="va-resource-image" src={fileUrl(project.id, resource.id)} alt={resource.name} />}
    {(resource.error || playbackError) && <FailureNotice message={resource.error || playbackError} code={resource.error ? latestJob?.error_code : undefined} diagnostics={support} />}{resource.warnings.map((warning, index) => <p className="va-notice" key={index}>{warning}</p>)}
    {(recognizing || preparing || startingRecognition || startingPreparation) && <p className="va-assistant-working" role="status"><span className="va-spinner" />{preparing || startingPreparation ? 'Preparing media…' : 'Processing missing evidence… Saved results remain available.'}</p>}
    {evidence && <div className="va-evidence-summary" aria-label="Recognition summary">{origin && <p>{origin}</p>}<p>{coverageMessage('speech', evidence.coverage.speech ?? 'not_analyzed', evidence.events.some(event => event.kind === 'speech'), evidence.diagnostics?.speech)}</p><p>{coverageMessage('visual', evidence.coverage.visual_action ?? evidence.coverage.visual ?? evidence.coverage.vision ?? 'not_analyzed', evidence.events.some(event => event.kind === 'visual'))}</p></div>}
    {(historicalEvidence || (!showLatest && citedExtraction)) && <div className="va-notice">Showing the exact historical evidence cited by this output.<button onClick={() => setShowLatest(true)}>View latest evidence</button></div>}
    {editing && latestEvidence ? <EvidenceEditor key={`${resource.id}:${latestEvidence.revision}`} project={project} resource={resource} mutate={mutate} onClose={() => setEditing(false)} /> : editingDocument ? <DocumentEditor project={project} resource={resource} mutate={mutate} onClose={() => setEditingDocument(false)} /> : <>
      <div className="va-tabs" role="tablist" aria-label="Resource details">{(resource.kind === 'video' || resource.kind === 'audio' ? [['speech', 'Transcript'], ['on_screen_text', 'Screen text'], ['visual', 'Visuals'], ['details', 'Details']] : [['document', 'Extracted text'], ['details', 'Details']]).map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id || (tab === 'speech' && id === 'document')} onClick={() => setTab(id)}>{label}</button>)}</div>
      {tab === 'details' ? <dl className="va-resource-details"><dt>Origin</dt><dd>{resource.origin === 'upload' ? 'Uploaded file' : resource.origin === 'legacy' ? 'Imported from earlier workspace' : 'Imported source'}</dd><dt>Size</dt><dd>{(resource.size_bytes / 1024 / 1024).toFixed(2)} MB</dd><dt>Original</dt><dd>Project-owned local copy</dd>{resource.duration_seconds != null && <><dt>Duration</dt><dd>{time(resource.duration_seconds)}</dd></>}{resource.source_url && <><dt>Source</dt><dd><a href={/^https?:\/\//.test(resource.source_url) ? resource.source_url : undefined} target="_blank" rel="noreferrer">{resource.source_url}</a></dd></>}{resource.provenance && <><dt>Provenance</dt><dd>{resource.provenance}</dd></>}<dt>Fingerprint</dt><dd className="va-hash">{resource.sha256}</dd></dl> : resource.kind === 'video' || resource.kind === 'audio' ? <div className="va-transcript">{evidence?.events.filter(event => event.kind === tab || (tab === 'visual' && event.kind === 'sound')).map(event => <article key={event.id}><button className="va-timecode" onClick={() => seek(event.start_seconds)} aria-label={`Seek to ${time(event.start_seconds)}`}>{time(event.start_seconds)}</button><div><p>{event.text}</p>{event.interpretation && <small>Interpretation: {event.interpretation}</small>}</div></article>)}{!evidence && <p className="va-muted">Select this resource and analyze it to extract speech and visual evidence.</p>}{evidence && !evidence.events.some(event => event.kind === tab) && <p className="va-muted">{coverageMessage(tab, evidence.coverage[tab] ?? 'not_analyzed', false, evidence.diagnostics?.[tab])}</p>}{evidence && <details><summary>Coverage and limitations</summary><dl>{Object.entries(evidence.coverage).map(([key, value]) => <div key={key}><dt>{channelLabel[key] ?? 'Evidence'}</dt><dd>{coverageMessage(key, value, evidence.events.some(event => event.kind === key), evidence.diagnostics?.[key])}</dd></div>)}</dl><SupportDetails diagnostics={support} label="Support diagnostics" />{evidence.limitations.map((item, index) => <p key={index}>{failureMessage(item)}</p>)}</details>}</div> : <div className="va-document-blocks">{documentBlocks.map(block => <article key={block.id}><small>{block.locator}</small><p>{block.text}</p></article>)}{!resource.blocks.length && <p className="va-muted">{resource.status === 'processing' || resource.status === 'stored' ? 'Extracting the document…' : 'No text was extracted. The original file is preserved.'}</p>}</div>}
      <div className="va-inspector-actions">{['video', 'audio'].includes(resource.kind) && <button disabled={recognizing || preparing || startingRecognition || startingPreparation} onClick={() => void retryRecognition()}>{recognizing || startingRecognition ? 'Recognizing…' : needsSpeech ? 'Retry transcription' : latestEvidence ? 'Retry recognition' : 'Extract speech / visuals'}</button>}{latestEvidence && !historicalEvidence && <><button onClick={() => setEditing(true)}>Correct text / timing</button><button disabled={latestEvidence.reviewed} onClick={() => void mutate(`/resources/${resource.id}/evidence/review`)}>{latestEvidence.reviewed ? 'Evidence reviewed' : 'Use reviewed evidence'}</button></>}{resource.blocks.length > 0 && (showLatest || !citedExtraction) && <button onClick={() => setEditingDocument(true)}>Correct extraction</button>}<button disabled={recognizing || preparing || startingRecognition || startingPreparation} onClick={() => void prepare()}>{preparing || startingPreparation ? 'Preparing…' : ['video', 'audio'].includes(resource.kind) ? 'Rebuild media preview' : 'Retry extraction'}</button><a className="va-button-link" href={fileUrl(project.id, resource.id)} target="_blank" rel="noreferrer">Open original</a><input ref={relink} className="va-sr-only" tabIndex={-1} type="file" onChange={async event => { const file = event.target.files?.[0]; if (!file) return; const body = new FormData(); body.append('file', file); const saved = await mutate(`/resources/${resource.id}/relink`, body); if (saved) setPlaybackError(''); }} /><button onClick={() => relink.current?.click()}>Relink original</button></div>
    </>}
  </aside>;
}

export default function Resources({ project, mutate, source, onAnalyze }: { project: Project; mutate: Mutate; source: SourceRef | null; onAnalyze: () => void }) {
  const [category, setCategory] = useState('all');
  const [search, setSearch] = useState('');
  const [preview, setPreview] = useState<string | null>(project.resources[0]?.id ?? null);
  const [selection, setSelection, flushSelection, selectionConflict, reloadSelection] = useDraft(project, 'reference-selection', { resource_ids: project.selection.resource_ids, content_id: '' }, mutate);
  const [uploading, setUploading] = useState(false);
  const [running, setRunning] = useState(false);
  const [visualOnly, setVisualOnly] = useState(false);
  const visualChoice = project.resources.some(resource => selection.resource_ids.includes(resource.id) && ['failed', 'partial'].includes(resource.evidence.at(-1)?.coverage.speech ?? '') && resource.evidence.at(-1)?.events.some(event => ['visual', 'on_screen_text'].includes(event.kind)));
  useEffect(() => setVisualOnly(false), [selection.resource_ids.join(',')]); // eslint-disable-line react-hooks/exhaustive-deps
  const upload = useRef<HTMLInputElement>(null);
  useEffect(() => { if (source?.resource_id) setPreview(source.resource_id); }, [source]);
  const selected = project.resources.find(resource => resource.id === preview) ?? project.resources[0];
  const visible = project.resources.filter(resource => (category === 'all' || resource.role === category) && resource.name.toLowerCase().includes(search.toLowerCase()));
  const importFiles = async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    for (const file of Array.from(files)) {
      const body = new FormData(); body.append('file', file); body.append('role', category === 'asset' ? 'asset' : /\.(mp4|mov|webm|mkv|mp3|wav|m4a|aac|ogg|flac)$/i.test(file.name) ? 'reference' : 'document');
      const saved = await mutate('/resources', body); if (saved) setPreview(saved.resources.at(-1)?.id ?? null);
    }
    setUploading(false);
  };
  const saveSelection = async () => await flushSelection() ? mutate('/selection', { resource_ids: selection.resource_ids, content_id: selection.content_id || null }) : null;
  const analyze = async () => {
    setRunning(true);
    const saved = await saveSelection();
    if (saved) { const started = await mutate('/analyze', { resource_ids: selection.resource_ids, content_id: selection.content_id || null, visual_only: visualOnly }); if (started) { await mutate('', { active_content_id: selection.content_id || null }, 'PATCH'); onAnalyze(); } }
    setRunning(false);
  };
  return <div className="va-resources"><section className="va-library va-glass"><div className="va-page-heading"><div><h1>Resource library</h1><p>Choose the references to analyze together.</p></div></div><div className="va-tabs">{[['all', 'All resources'], ['reference', 'References'], ['document', 'Documents'], ['asset', 'Production assets']].map(([id, label]) => <button key={id} className={category === id ? 'active' : ''} onClick={() => setCategory(id)}>{label}</button>)}</div><div className="va-resource-tools"><label className="va-search"><Icon name="search" /><input aria-label="Search resources" placeholder="Search resources" value={search} onChange={event => setSearch(event.target.value)} /></label><input ref={upload} type="file" multiple tabIndex={-1} className="va-sr-only" onChange={event => { void importFiles(event.target.files); event.target.value = ''; }} /><button className="va-primary" disabled={uploading} onClick={() => upload.current?.click()}><Icon name="upload" />{uploading ? 'Importing…' : 'Upload files'}</button></div>
    {!project.resources.length ? <Empty title="Bring your materials together"><p>Add briefs, product documents, references, and production assets. Original files are copied into this project.</p><button onClick={() => upload.current?.click()}>Choose files</button></Empty> : <div className="va-resource-grid">{visible.map(resource => <article className={`va-resource-card ${selection.resource_ids.includes(resource.id) ? 'selected' : ''} ${selected?.id === resource.id ? 'previewing' : ''}`} key={resource.id}><div className="va-resource-card-heading"><label><input type="checkbox" aria-label={`Select ${resource.name}`} disabled={!['video', 'audio'].includes(resource.kind)} checked={selection.resource_ids.includes(resource.id)} onChange={event => setSelection({ ...selection, resource_ids: event.target.checked ? [...selection.resource_ids, resource.id] : selection.resource_ids.filter(id => id !== resource.id) })} /><span>{resource.name}</span></label><Badge tone={resource.origin === 'upload' ? 'success' : ''}>{resource.origin === 'upload' ? 'Uploaded' : resource.origin === 'legacy' ? 'Imported' : 'Discovery import'}</Badge></div><button className="va-resource-preview" onClick={() => setPreview(resource.id)} aria-label={`Preview ${resource.name}`}>{resource.thumbnail_path || resource.kind === 'image' ? <img src={fileUrl(project.id, resource.id, resource.thumbnail_path ? 'thumbnail' : 'original')} alt="" /> : <Icon name={['video', 'audio'].includes(resource.kind) ? 'play' : 'file'} size={38} />}{resource.duration_seconds != null && <span className="va-duration"><Icon name="play" size={12} />{time(resource.duration_seconds)}</span>}</button><div className="va-resource-card-footer"><span>{resource.kind}</span><Badge tone={['failed', 'unsupported', 'missing', 'partial'].includes(resource.status) || Object.values(resource.evidence.at(-1)?.coverage ?? {}).some(value => ['failed', 'partial', 'error'].includes(value)) ? 'warning' : ''}>{resourceMessage(resource)}</Badge></div>{resource.error && <p className="va-resource-error">{failureMessage(resource.error)}</p>}</article>)}</div>}
    {visualChoice && <label className="va-visual-choice"><input type="checkbox" checked={visualOnly} onChange={event => setVisualOnly(event.target.checked)} />Continue with visual evidence only<span>Speech is unavailable. The analysis will retain this limitation.</span></label>}<DraftConflict conflict={selectionConflict} reload={reloadSelection} /><footer className="va-selection-bar"><div><strong>{selection.resource_ids.length} selected</strong><label>For <select aria-label="Reference selection for" value={selection.content_id} onChange={event => { const content = project.contents.find(item => item.id === event.target.value); setSelection({ content_id: event.target.value, resource_ids: content?.selection.resource_ids ?? project.selection.resource_ids }); }}><option value="">Project exploration</option>{project.contents.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label></div><div className="va-actions"><button onClick={() => void saveSelection()}>Save selection</button><button className="va-primary" disabled={!selection.resource_ids.length || running} onClick={() => void analyze()}><Icon name="play" />{running ? 'Starting…' : `Analyze selected (${selection.resource_ids.length})`}</button></div></footer>
  </section>{selected && <Inspector key={selected.id} project={project} resource={selected} source={source} mutate={mutate} />}</div>;
}
