import { useEffect, useRef, useState } from 'react';
import type { Project, Resource, ResourceFolder, SourceRef } from './contracts';
import { DraftConflict, Empty, Icon, date, time } from './Common';
import { call, useDraft, type Mutate } from './client';
import ResourceInspector from './ResourceReview';
import SourceReview from './SourceReview';
import { fileSize, folderContains, folderIsTrashed, folderPath, recordedImportDate, resourceIsTrashed } from './resourceLibrary';
import { resourceMessage } from './status';
import SpeechModel, { type SpeechModelId } from './SpeechModel';
import './resources.css';

type Command = { kind: 'new-folder' | 'rename-folder' | 'move-folder' | 'trash-folder' | 'restore-folder'; folder?: ResourceFolder } | { kind: 'rename-file' | 'move-files' | 'trash-files' | 'restore-files'; ids: string[] };
export default function Resources({ project, mutate, source, onAnalyze, onCloseSource, sourceReturnLabel, onAttachResource }: { project: Project; mutate: Mutate; source: SourceRef | null; onAnalyze: () => void; onCloseSource?: () => void; sourceReturnLabel?: string; onAttachResource?: (resourceId: string) => void }) {
  const [view, setView] = useDraft(project, 'resource-library-view', { directory: 'all', layout: 'list' as 'list' | 'grid', focus_id: null as string | null, review_id: null as string | null, citation: null as SourceRef | null }, mutate);
  const directory = view.directory;
  const layout = view.layout;
  const focusId = view.focus_id;
  const reviewId = view.review_id;
  const setDirectory = (directory: string) => setView({ ...view, directory, review_id: null, citation: null });
  const setLayout = (layout: 'list' | 'grid') => setView({ ...view, layout });
  const setFocusId = (focus_id: string | null) => setView({ ...view, focus_id });
  const setReviewId = (review_id: string | null) => setView({ ...view, review_id, citation: null });
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<'name' | 'created_at' | 'size_bytes' | 'duration_seconds'>('name');
  const [descending, setDescending] = useState(false);
  const oldSelection = project.editor_drafts['reference-selection']?.resource_ids;
  const initialSelection = Array.isArray(oldSelection) ? oldSelection.filter((id): id is string => typeof id === 'string' && project.resources.some(item => item.id === id)) : project.selection.resource_ids;
  const [selection, setSelection, flushSelection, selectionConflict, reloadSelection] = useDraft(project, 'filesystem-selection', { resource_ids: initialSelection }, mutate);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState('');
  const [uploadReceipts, setUploadReceipts] = useState<{ name: string; message: string }[]>([]);
  const [limits, setLimits] = useState<{ max_bytes: number; max_duration_seconds: number; max_width: number; max_height: number } | null>(null);
  const [speech, setSpeech] = useDraft(project, 'recognition-settings', { transcription_model: 'whisper-1' as SpeechModelId }, mutate);
  const [working, setWorking] = useState(false);
  const [command, setCommand] = useState<Command | null>(null);
  const [commandError, setCommandError] = useState('');
  const [analysisError, setAnalysisError] = useState('');
  const [name, setName] = useState('');
  const [destination, setDestination] = useState('folder_inbox');
  const [scope, setScope] = useState('');
  const [visualOnly, setVisualOnly] = useState(false);
  const [savedOnly, setSavedOnly] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const analyzeDialog = useRef<HTMLDialogElement>(null);
  const upload = useRef<HTMLInputElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => { let mounted = true; void call<{ media_limits?: typeof limits }>('/capabilities').then(value => { if (mounted) setLimits(value.media_limits ?? null); }).catch(() => { /* The server still validates each import. */ }); return () => { mounted = false; }; }, []);
  useEffect(() => { if (source?.resource_id) setView({ ...view, review_id: source.resource_id, focus_id: source.resource_id, citation: source }); }, [source]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (command) dialog.current?.showModal(); }, [command]);
  const folder = project.resource_folders.find(item => item.id === directory);
  const focused = project.resources.find(item => item.id === focusId);
  const reviewed = project.resources.find(item => item.id === reviewId);
  const reviewSource = source?.resource_id === reviewId ? source : view.citation?.resource_id === reviewId ? view.citation : null;
  const inTrash = directory === 'trash';
  const checked = project.resources.filter(item => selection.resource_ids.includes(item.id));
  const media = checked.filter(item => ['video', 'audio'].includes(item.kind) && !resourceIsTrashed(project, item));
  const hasSavedEvidence = media.some(item => Boolean(item.evidence.at(-1)?.events.length));
  const visible = project.resources.filter(item => resourceIsTrashed(project, item) === inTrash && (directory === 'all' || inTrash || item.folder_id === directory) && item.name.toLocaleLowerCase().includes(search.toLocaleLowerCase())).sort((a, b) => {
    const value = sort === 'name' || sort === 'created_at' ? String(a[sort]).localeCompare(String(b[sort])) : (a[sort] ?? -1) - (b[sort] ?? -1);
    return descending ? -value : value;
  });
  const folders = project.resource_folders.filter(item => inTrash ? Boolean(item.trashed_at) : directory !== 'all' && item.parent_id === directory && !folderIsTrashed(project, item.id));
  const activeFolders = project.resource_folders.filter(item => !folderIsTrashed(project, item.id));
  const hasPartialSpeech = media.some(item => ['failed', 'partial', 'error'].includes(item.evidence.at(-1)?.coverage.speech ?? '') && item.evidence.at(-1)?.events.some(event => ['visual', 'on_screen_text'].includes(event.kind)));
  const chosenIds = checked.length ? checked.map(item => item.id) : focused ? [focused.id] : [];
  const select = (resource: Resource, checked: boolean) => setSelection({ resource_ids: checked ? [...new Set([...selection.resource_ids, resource.id])] : selection.resource_ids.filter(id => id !== resource.id) });
  const open = (resource: Resource) => setView({ ...view, focus_id: resource.id, review_id: resource.id, citation: null });
  const begin = (next: Command) => {
    setName('folder' in next ? next.folder?.name ?? '' : next.kind === 'rename-file' ? project.resources.find(item => item.id === next.ids[0])?.name ?? '' : '');
    setDestination(next.kind === 'move-folder' ? next.folder?.parent_id ?? '' : folder && !folderIsTrashed(project, folder.id) ? folder.id : 'folder_inbox'); setCommandError(''); setCommand(next);
  };
  const finish = async () => {
    if (!command || working) return;
    setWorking(true);
    try {
      let saved: Project | null = null;
      if (command.kind === 'new-folder') saved = await mutate('/folders', { name: name.trim(), parent_id: folder?.id ?? null });
      else if (command.kind === 'rename-folder') saved = await mutate(`/folders/${command.folder!.id}`, { name: name.trim() }, 'PATCH');
      else if (command.kind === 'move-folder') saved = await mutate(`/folders/${command.folder!.id}`, { parent_id: destination || null }, 'PATCH');
      else if (command.kind === 'trash-folder' || command.kind === 'restore-folder') saved = await mutate(`/folders/${command.folder!.id}/${command.kind === 'trash-folder' ? 'trash' : 'restore'}`);
      else if (command.kind === 'rename-file') saved = await mutate(`/resources/${command.ids[0]}`, { name: name.trim() }, 'PATCH');
      else if (command.kind === 'move-files') saved = await mutate('/resources/move', { resource_ids: command.ids, folder_id: destination });
      else if ('ids' in command) {
        for (const id of command.ids) {
          saved = await mutate(`/resources/${id}/${command.kind === 'trash-files' ? 'trash' : 'restore'}`);
          if (!saved) break;
        }
      }
      if (saved) { if (command.kind === 'trash-folder') setDirectory('all'); dialog.current?.close(); heading.current?.focus(); }
      else setCommandError('The change could not be completed. Review the current items, name and destination before trying again.');
    } finally { setWorking(false); }
  };
  const importFiles = async (files: FileList | null) => {
    if (!files) return; setUploading(true); setUploadReceipts([]);
    const imports = Array.from(files);
    try {
      for (const [index, file] of imports.entries()) {
        setUploadProgress(`Importing ${index + 1} of ${imports.length} · ${file.name}`);
        if (limits && file.size > limits.max_bytes) {
          setUploadReceipts(previous => [...previous, { name: file.name, message: `Not imported: exceeds the configured ${Math.floor(limits.max_bytes / 1024 / 1024)} MiB limit.` }]);
          continue;
        }
        const body = new FormData(); body.append('file', file);
        if (folder && !folderIsTrashed(project, folder.id)) body.append('folder_id', folder.id);
        let failure = 'The file was not imported. Review the source format and try again.';
        const saved = await mutate('/resources', body, undefined, { localError: true, onError: message => { failure = message; } });
        if (saved) setFocusId(saved.resources.at(-1)?.id ?? null);
        setUploadReceipts(previous => [...previous, { name: file.name, message: saved ? 'Imported. Local media preparation has its own Activity task.' : `Not imported: ${failure}` }]);
      }
    } finally { setUploading(false); setUploadProgress(''); if (upload.current) upload.current.value = ''; }
  };
  const analyze = async () => {
    if (!media.length || working || !await flushSelection()) return;
    setWorking(true); setAnalysisError('');
    try {
      const resource_ids = media.map(item => item.id); const content_id = scope || null;
      const errors = { localError: true, onError: setAnalysisError };
      const selected = await mutate('/selection', { resource_ids, content_id }, undefined, errors);
      if (selected && await mutate('/analyze', { resource_ids, content_id, visual_only: visualOnly, synthesis_only: savedOnly, ...(visualOnly || savedOnly ? {} : { transcription_model: speech.transcription_model }) }, undefined, errors)) { analyzeDialog.current?.close(); onAnalyze(); }
    } finally { setWorking(false); }
  };
  const tree = (parent: string | null, depth = 0, visited = new Set<string>()): React.ReactNode => project.resource_folders.filter(item => item.parent_id === parent && !folderIsTrashed(project, item.id) && !visited.has(item.id)).map(item => <div key={item.id}><button type="button" className={directory === item.id ? 'active' : ''} style={{ paddingInlineStart: 12 + depth * 13 }} aria-current={directory === item.id ? 'location' : undefined} onClick={() => setDirectory(item.id)}><Icon name="resources" size={17} /><span>{item.name}</span></button>{tree(item.id, depth + 1, new Set([...visited, item.id]))}</div>);
  const row = (resource: Resource) => <tr key={resource.id} className={`${focusId === resource.id ? 'focused' : ''} ${selection.resource_ids.includes(resource.id) ? 'checked' : ''}`} onDoubleClick={() => open(resource)}>
    <td><input type="checkbox" aria-label={`Select ${resource.name}`} checked={selection.resource_ids.includes(resource.id)} onChange={event => select(resource, event.target.checked)} /></td><th scope="row"><button type="button" className="va-file-name" aria-label={`Focus ${resource.name}`} aria-pressed={focusId === resource.id} onClick={() => setFocusId(resource.id)} onKeyDown={event => { if (event.key === 'Enter' && event.altKey) { event.preventDefault(); open(resource); } }}><Icon name={['video', 'audio'].includes(resource.kind) ? 'play' : 'file'} size={20} /><span>{resource.name}</span></button></th><td data-label="Type">{resource.mime_type !== 'application/octet-stream' ? resource.mime_type : resource.kind}</td><td data-label="Imported">{recordedImportDate(resource) ? date(recordedImportDate(resource)!) : '—'}</td><td data-label="Size">{fileSize(resource)}</td><td data-label="Duration">{resource.duration_seconds != null ? time(resource.duration_seconds) : '—'}</td><td data-label="Status"><span>{resourceIsTrashed(project, resource) ? 'In Trash' : resourceMessage(resource)}</span></td>
  </tr>;

  if (reviewId) return <div className="va-library-review"><button type="button" className="va-back-to-pool" onClick={() => { setReviewId(null); if (source?.resource_id) onCloseSource?.(); }}><Icon name="back" />{source?.resource_id ? sourceReturnLabel ?? 'Back to previous view' : 'Back to Media Pool'}</button>{reviewed ? ['video', 'audio'].includes(reviewed.kind) ? <SourceReview key={reviewed.id} project={project} resource={reviewed} source={reviewSource} mutate={mutate} speechModel={speech.transcription_model} onSpeechModel={transcription_model => setSpeech({ transcription_model })} /> : <ResourceInspector key={reviewed.id} project={project} resource={reviewed} source={reviewSource} mutate={mutate} /> : <Empty title="Source unavailable"><p>The cited resource is not present in this project. No substitute was opened.</p></Empty>}</div>;
  return <section className="va-media-pool va-glass">
    <div className="va-page-heading"><div><h1 ref={heading} tabIndex={-1}>Media Pool</h1><p>Organize your files, then choose references for analysis.</p></div><input ref={upload} className="va-sr-only" tabIndex={-1} type="file" multiple onChange={event => { void importFiles(event.target.files); event.target.value = ''; }} /><button type="button" className="va-primary" disabled={uploading || inTrash} onClick={() => upload.current?.click()}><Icon name="upload" />{uploading ? 'Importing…' : 'Upload files'}</button></div>
    <p className="va-muted va-import-limits">{limits ? `Per file: ${Math.floor(limits.max_bytes / 1024 / 1024)} MiB maximum; media up to ${limits.max_duration_seconds} seconds and ${limits.max_width} × ${limits.max_height}. Upload saves an original; analysis is a separate action.` : 'Each file is validated by the local server. Uploading does not start API analysis.'}</p>
    {uploadProgress && <p role="status">{uploadProgress}</p>}
    {uploadReceipts.length > 0 && <details className="va-upload-results" open><summary>Upload results · {uploadReceipts.length} files checked</summary><ul>{uploadReceipts.map((receipt, index) => <li key={index}><strong>{receipt.name}</strong> — {receipt.message}</li>)}</ul></details>}
    <div className="va-pool-layout"><details className="va-folder-sidebar" open><summary>Folders</summary><nav aria-label="Resource folders"><button type="button" className={directory === 'all' ? 'active' : ''} onClick={() => setDirectory('all')}><Icon name="resources" size={18} />All files</button>{tree(null)}<button type="button" onClick={() => begin({ kind: 'new-folder' })}><Icon name="plus" size={18} />New folder</button><button type="button" className={inTrash ? 'active' : ''} onClick={() => setDirectory('trash')}><Icon name="trash" size={18} />Trash</button></nav></details>
    <div className="va-pool-content"><div className="va-pool-breadcrumb"><strong>{inTrash ? 'Trash' : folder ? folderPath(project, folder) : 'All files'}</strong>{folder && <details><summary aria-label="Folder actions">Folder actions</summary><div className="va-actions"><button type="button" onClick={() => begin({ kind: 'rename-folder', folder })}>Rename folder</button><button type="button" onClick={() => begin({ kind: 'move-folder', folder })}>Move folder</button><button type="button" onClick={() => begin({ kind: 'trash-folder', folder })}>Move folder to Trash</button></div></details>}</div>
      <div className="va-pool-tools"><label className="va-search"><Icon name="search" /><input aria-label="Search files" placeholder="Search files…" value={search} onChange={event => setSearch(event.target.value)} /></label><div role="group" aria-label="File view"><button type="button" aria-pressed={layout === 'list'} onClick={() => setLayout('list')}>List</button><button type="button" aria-pressed={layout === 'grid'} onClick={() => setLayout('grid')}>Grid</button></div><label className="va-sr-only" htmlFor={`files-sort-${project.id}`}>Sort files</label><select id={`files-sort-${project.id}`} value={sort} onChange={event => setSort(event.target.value as typeof sort)}><option value="name">Name</option><option value="created_at">Imported</option><option value="size_bytes">Size</option><option value="duration_seconds">Duration</option></select><button type="button" aria-label={descending ? 'Sort ascending' : 'Sort descending'} onClick={() => setDescending(!descending)}>{descending ? '↓' : '↑'}</button></div>
      <div className="va-pool-file-actions" aria-label="File actions"><button type="button" disabled={!focused} onClick={() => focused && open(focused)}>{focused && ['video', 'audio'].includes(focused.kind) ? 'Open in timeline' : 'Open file'}</button>{onAttachResource && focused && ['document', 'image'].includes(focused.kind) && !resourceIsTrashed(project, focused) && <button type="button" onClick={() => onAttachResource(focused.id)}>Attach in Overview</button>}<button type="button" disabled={!focused || inTrash} onClick={() => focused && begin({ kind: 'rename-file', ids: [focused.id] })}>Rename file</button><button type="button" disabled={!chosenIds.length || inTrash} onClick={() => begin({ kind: 'move-files', ids: chosenIds })}>Move to</button><button type="button" disabled={!chosenIds.length} onClick={() => begin({ kind: inTrash ? 'restore-files' : 'trash-files', ids: chosenIds })}>{inTrash ? 'Restore file' : 'Move to Trash'}</button></div>
      {folders.length > 0 && <div className="va-pool-subfolders">{folders.map(item => <div key={item.id}><button type="button" onClick={() => inTrash ? begin({ kind: 'restore-folder', folder: item }) : setDirectory(item.id)}><Icon name="resources" />{item.name}{inTrash && ' · Restore folder'}</button></div>)}</div>}
      {!visible.length ? <Empty title={inTrash ? 'No files in Trash' : 'No files here'}><p>{search ? 'Try another file name.' : inTrash ? 'Files and evidence are retained when you move them to Trash.' : 'Upload files into this folder. Uploads from All files go to Inbox.'}</p></Empty> : layout === 'list' ? <div className="va-pool-table-scroll" tabIndex={0} role="region" aria-label="Project files"><table className="va-pool-table"><caption className="va-sr-only">Files in {folder?.name ?? (inTrash ? 'Trash' : 'All files')}</caption><thead><tr><th scope="col">Select</th><th scope="col">Name</th><th scope="col">Type</th><th scope="col">Imported</th><th scope="col">Size</th><th scope="col">Duration</th><th scope="col">Status</th></tr></thead><tbody>{visible.map(row)}</tbody></table></div> : <div className="va-pool-grid">{visible.map(resource => <article key={resource.id} className={focusId === resource.id ? 'focused' : ''}><label><input type="checkbox" aria-label={`Select ${resource.name}`} checked={selection.resource_ids.includes(resource.id)} onChange={event => select(resource, event.target.checked)} />Select file</label><button type="button" className="va-file-name" aria-label={`Focus ${resource.name}`} aria-pressed={focusId === resource.id} onClick={() => setFocusId(resource.id)} onDoubleClick={() => open(resource)}><Icon name={['video', 'audio'].includes(resource.kind) ? 'play' : 'file'} size={28} /><strong>{resource.name}</strong></button><p>{resource.kind} · {fileSize(resource)}{resource.duration_seconds != null ? ` · ${time(resource.duration_seconds)}` : ''}</p><small>{resourceMessage(resource)}</small></article>)}</div>}
      {focused && <p className="va-pool-focus" role="status"><strong>Focused:</strong> {focused.name} · {resourceMessage(focused)}. Opening a file does not change the checked references.</p>}
      <DraftConflict conflict={selectionConflict} reload={reloadSelection} />
      {checked.length > 0 && <footer className="va-pool-selection"><div><strong>{checked.length} {checked.length === 1 ? 'file' : 'files'} selected</strong><span>{media.length} analyzable {media.length === 1 ? 'reference' : 'references'}</span></div><div className="va-actions"><button type="button" onClick={() => setSelection({ resource_ids: [] })}>Clear selection</button><button type="button" className="va-primary" disabled={!media.length || working} onClick={() => { setScope(''); setVisualOnly(false); setSavedOnly(false); setAnalysisError(''); analyzeDialog.current?.showModal(); }}>Analyze {media.length} {media.length === 1 ? 'reference' : 'references'}</button></div></footer>}
    </div></div>
    <dialog ref={dialog} className="va-pool-dialog" aria-labelledby={`file-command-${project.id}`} onClose={() => setCommand(null)}><form onSubmit={event => { event.preventDefault(); void finish(); }}><h2 id={`file-command-${project.id}`}>{command?.kind === 'new-folder' ? 'New folder' : command?.kind === 'rename-folder' ? 'Rename folder' : command?.kind === 'move-folder' ? 'Move folder' : command?.kind === 'rename-file' ? 'Rename file' : command?.kind === 'move-files' ? 'Move files' : command?.kind.startsWith('restore') ? 'Restore from Trash' : 'Move to Trash'}</h2>
      {command && ['new-folder', 'rename-folder', 'rename-file'].includes(command.kind) && <><label htmlFor={`resource-name-${project.id}`}>Name</label><input id={`resource-name-${project.id}`} value={name} onChange={event => setName(event.target.value)} required maxLength={240} /></>}
      {command && ['move-folder', 'move-files'].includes(command.kind) && <><label htmlFor={`resource-destination-${project.id}`}>Destination folder</label><select id={`resource-destination-${project.id}`} value={destination} onChange={event => setDestination(event.target.value)}>{command.kind === 'move-folder' && <option value="">Root folders</option>}{activeFolders.filter(item => command.kind !== 'move-folder' || !command.folder || !folderContains(project, command.folder.id, item.id)).map(item => <option key={item.id} value={item.id}>{folderPath(project, item)}</option>)}</select></>}
      {command?.kind.startsWith('trash') && <p>Original files, saved evidence and historical references are retained. References used by saved work will be marked unavailable until restored. No permanent deletion is performed.</p>}
      {command?.kind.startsWith('restore') && <p>Restore this item to its existing folder. A trashed parent folder must also be restored.</p>}
      {commandError && <p className="va-notice" role="alert">{commandError}</p>}
      <div className="va-actions"><button type="button" autoFocus disabled={working} onClick={() => dialog.current?.close()}>Cancel</button><button type="submit" className="va-primary" disabled={working || (Boolean(command && ['new-folder', 'rename-folder', 'rename-file'].includes(command.kind)) && !name.trim())}>{working ? 'Saving…' : command?.kind.startsWith('trash') ? 'Move to Trash' : command?.kind.startsWith('restore') ? 'Restore' : 'Save'}</button></div></form></dialog>
    <dialog ref={analyzeDialog} className="va-pool-dialog" aria-labelledby={`analyze-confirm-${project.id}`}><form onSubmit={event => { event.preventDefault(); void analyze(); }}><h2 id={`analyze-confirm-${project.id}`}>Analyze selected references</h2><p>Only these {media.length} media files will be analyzed. Other checked files are retained for file operations.</p><ul>{media.map(item => <li key={item.id}>{item.name}</li>)}</ul><label htmlFor={`analysis-scope-${project.id}`}>Analysis for</label><select id={`analysis-scope-${project.id}`} value={scope} onChange={event => setScope(event.target.value)}><option value="">Project exploration</option>{project.contents.filter(item => !item.trashed_at).map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select><label className="va-visual-choice"><input type="checkbox" checked={savedOnly} disabled={working || !hasSavedEvidence} onChange={event => setSavedOnly(event.target.checked)} />Use saved evidence only — skip visual and speech recognition.</label>{savedOnly && <p className="va-muted">The report uses available saved observations and keeps coverage gaps explicit. Retry a source separately to improve its transcript.</p>}<SpeechModel id={`analysis-speech-model-${project.id}`} value={speech.transcription_model} onChange={transcription_model => setSpeech({ transcription_model })} disabled={working || visualOnly || savedOnly} />{hasPartialSpeech && <label className="va-visual-choice"><input type="checkbox" checked={visualOnly} onChange={event => setVisualOnly(event.target.checked)} />Continue with visual evidence only. Keep the incomplete speech limitation in the report.</label>}{analysisError && <p className="va-error" role="alert">{analysisError}</p>}<p className="va-muted">Analysis uses your configured API. Choosing a scope does not switch the Video selected for Production.</p><div className="va-actions"><button type="button" autoFocus disabled={working} onClick={() => analyzeDialog.current?.close()}>Cancel</button><button type="submit" className="va-primary" disabled={working || !media.length}>{working ? 'Starting…' : savedOnly ? 'Generate from saved evidence' : 'Start analysis'}</button></div></form></dialog>
  </section>;
}
