import { useEffect, useRef, useState } from 'react';
import ApiConnection, { ApiConnectionButton, ConnectionHelp } from './ApiConnection';
import { Brand, Icon, Badge, date, type SourceAction } from './project/Common';
import { call, fileUrl, recentProjectOpenings, useProjectController } from './project/client';
import type { Project, SourceRef } from './project/contracts';
import Overview from './project/Overview';
import Resources from './project/Resources';
import AnalysisView from './project/AnalysisView';
import ContentPlan from './project/ContentPlan';
import ProductionView from './project/ProductionView';
import ActivityPanel from './project/ActivityPanel';
import './project/workspace.css';
import { failureMessage } from './project/status';

const destinations = [ ['overview', 'Overview'], ['resources', 'Resources'], ['discover', 'Discover'], ['analysis', 'Analysis'], ['content', 'Content plan'], ['production', 'Production'] ] as const;

function Dashboard({ projects, loading, onOpen, onRefresh, onError }: { projects: Project[]; loading: boolean; onOpen: (id: string) => Promise<void>; onRefresh: () => Promise<void>; onError: (message: string) => void }) {
  const [view, setView] = useState<'projects' | 'trash'>('projects');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('recent');
  const [recent] = useState(recentProjectOpenings);
  const [command, setCommand] = useState<{ kind: 'create' | 'rename' | 'trash'; project?: Project } | null>(null);
  const [title, setTitle] = useState('');
  const [pending, setPending] = useState(false);
  const projectDialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = projectDialog.current;
    if (command && dialog && !dialog.open) dialog.showModal();
    else if (!command && dialog?.open) dialog.close();
  }, [command]);
  const projectCommand = async (item: Project, action: 'duplicate' | 'restore' | 'trash') => {
    setPending(true);
    try { const next = await call<Project>(`/${item.id}/${action}`, { expected_version: item.version }); await onRefresh(); if (action === 'duplicate') await onOpen(next.id); }
    catch (failure) { onError(failure instanceof Error ? failure.message : 'Project action failed.'); }
    finally { setPending(false); }
  };
  const submit = async () => {
    if (!command || pending) return;
    if (command.kind === 'trash' && command.project) { await projectCommand(command.project, 'trash'); setCommand(null); return; }
    if (!title.trim()) return;
    setPending(true);
    try {
      const next = command.kind === 'create' ? await call<Project>('', { title: title.trim() }) : await call<Project>(`/${command.project!.id}`, { title: title.trim(), expected_version: command.project!.version }, 'PATCH');
      setCommand(null); await onRefresh(); if (command.kind === 'create') await onOpen(next.id);
    } catch (failure) { onError(failure instanceof Error ? failure.message : 'Could not save project.'); }
    finally { setPending(false); }
  };
  const filtered = projects.filter(item => Boolean(item.trashed_at) === (view === 'trash') && item.title.toLowerCase().includes(query.toLowerCase())).sort((a, b) => sort === 'name' ? a.title.localeCompare(b.title) : sort === 'recent' ? (recent[b.id] ?? b.updated_at).localeCompare(recent[a.id] ?? a.updated_at) : b.updated_at.localeCompare(a.updated_at));
  return <div className="va-dashboard"><aside className="va-rail"><nav aria-label="Project library"><button className={view === 'projects' ? 'active' : ''} onClick={() => setView('projects')}><Icon name="projects" />Projects</button><button className={view === 'trash' ? 'active' : ''} onClick={() => setView('trash')}><Icon name="trash" />Trash</button></nav><div className="va-rail-bottom"><ApiConnectionButton /><span>Stored on this computer</span></div></aside>
    <main id="va-library-main" className="va-dashboard-main" tabIndex={-1}><div className="va-page-heading"><div><h1>{view === 'trash' ? 'Project trash' : 'Your projects'}</h1><p>{view === 'trash' ? 'Your files and saved work are retained until restored.' : 'A workspace for every creative assignment.'}</p></div><button className="va-primary" onClick={() => { setTitle(''); setCommand({ kind: 'create' }); }}><Icon name="plus" />New project</button></div>
      <div className="va-dashboard-tools"><label className="va-search"><Icon name="search" /><input aria-label="Search projects" placeholder="Search projects" value={query} onChange={event => setQuery(event.target.value)} /></label><select aria-label="Sort projects" value={sort} onChange={event => setSort(event.target.value)}><option value="recent">Recently used</option><option value="updated">Recently updated</option><option value="name">Project name</option></select><span className="va-muted">{filtered.length} {filtered.length === 1 ? 'project' : 'projects'}</span></div>
      {loading ? <p role="status">Opening your project library…</p> : <div className="va-project-grid">{filtered.map(item => {
        const thumbnail = item.resources.find(resource => resource.thumbnail_path || resource.kind === 'image');
        const status = item.packs.length ? 'Production' : item.contents.length ? 'Planning' : item.resources.length ? 'Research' : 'Draft';
        return <article className="va-project-card" key={item.id}><button className="va-project-open" onClick={() => void onOpen(item.id)} disabled={Boolean(item.trashed_at)} aria-label={`Open ${item.title}`}><div className={`va-project-cover tint-${item.title.length % 4}`}>{thumbnail ? <img src={fileUrl(item.id, thumbnail.id, thumbnail.thumbnail_path ? 'thumbnail' : 'original')} alt="" /> : <Icon name={status === 'Production' ? 'production' : 'projects'} size={55} />}</div><div className="va-project-card-copy"><h2>{item.title}</h2><Badge>{status}</Badge><p>{item.resources.length} resources · {item.contents.filter(video => !video.trashed_at).length} videos</p><small>{recent[item.id] ? `Last opened ${date(recent[item.id])}` : `Updated ${date(item.updated_at)}`}</small></div></button>
          {item.trashed_at ? <button className="va-restore" disabled={pending} onClick={() => void projectCommand(item, 'restore')}>Restore project</button> : <details className="va-card-menu" onClick={event => { if ((event.target as HTMLElement).closest('button')) event.currentTarget.open = false; }}><summary aria-label={`Actions for ${item.title}`}>•••</summary><div><button onClick={() => { setTitle(item.title); setCommand({ kind: 'rename', project: item }); }}>Rename</button><button disabled={pending} onClick={() => void projectCommand(item, 'duplicate')}>Duplicate</button><button className="va-danger" onClick={() => setCommand({ kind: 'trash', project: item })}>Move to Trash</button></div></details>}
        </article>;
      })}{view === 'projects' && !query && <button className="va-new-card" onClick={() => { setTitle(''); setCommand({ kind: 'create' }); }}><Icon name="plus" size={45} /><span>Create a project</span></button>}</div>}
      {!loading && !filtered.length && (query || view === 'trash') && <p className="va-muted">{query ? 'No projects match your search.' : 'Trash is empty.'}</p>}
    </main>
    <dialog ref={projectDialog} className="va-modal va-project-dialog" aria-labelledby="project-dialog-title" onClose={event => { if (!event.currentTarget.open) setCommand(null); }} onCancel={event => { if (pending) event.preventDefault(); }}>{command && <form onSubmit={event => { event.preventDefault(); void submit(); }}><h2 id="project-dialog-title">{command.kind === 'create' ? 'Create a project' : command.kind === 'rename' ? 'Rename project' : `Move “${command.project?.title}” to Trash?`}</h2>{command.kind === 'trash' ? <p>The project, original files, and all saved work will be kept. Restore it from Trash at any time.</p> : <label>Project name<input autoFocus value={title} onChange={event => setTitle(event.target.value)} placeholder="Name your creative assignment" required /></label>}<div className="va-actions"><button type="button" onClick={() => setCommand(null)} disabled={pending}>Cancel</button><button className="va-primary" disabled={pending || (command.kind !== 'trash' && !title.trim())}>{pending ? 'Saving…' : command.kind === 'trash' ? 'Move to Trash' : command.kind === 'create' ? 'Create project' : 'Save name'}</button></div></form>}</dialog>
  </div>;
}

function Application() {
  const controller = useProjectController();
  const { project, mutate, saving, error } = controller;
  const [area, setArea] = useState('overview');
  const [source, setSource] = useState<SourceRef | null>(null);
  const [sourceReturn, setSourceReturn] = useState('resources');
  const sourceOrigin = useRef<HTMLElement | null>(null);
  const sourceProject = useRef<string | null>(null);
  const [settings, setSettings] = useState(false);
  const [activity, setActivity] = useState(false);
  const activityToggle = useRef<HTMLButtonElement>(null);
  const closeActivity = () => { setActivity(false); requestAnimationFrame(() => activityToggle.current?.focus()); };
  const [build, setBuild] = useState<{ version: string; source_commit: string | null }>({ version: '1.8.5', source_commit: null });
  const [migrationErrors, setMigrationErrors] = useState<string[]>([]);
  useEffect(() => { void call<{ version: string; source_commit: string | null; migration_errors: string[]; library_errors?: string[] }>('/capabilities').then(value => { setBuild(value); setMigrationErrors([...(value.migration_errors ?? []), ...(value.library_errors ?? [])]); }).catch(() => { /* Main project request reports connection errors. */ }); }, []);
  useEffect(() => { if (project) setArea(destinations.some(([id]) => id === project.workspace) ? project.workspace : 'overview'); }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const navigate = (next: string) => { setArea(next); void mutate('', { workspace: next }, 'PATCH'); };
  const onSource: SourceAction = value => { sourceProject.current = project?.id ?? null; sourceOrigin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null; setSourceReturn(area); setSource(value); navigate(value.resource_id ? 'resources' : 'overview'); };
  const closeSource = () => {
    const invoker = sourceOrigin.current;
    setSource(null); navigate(sourceReturn); sourceOrigin.current = null;
    requestAnimationFrame(() => {
      if (invoker?.isConnected && invoker.getClientRects().length) invoker.focus();
      else document.getElementById('va-workspace-main')?.focus();
    });
  };
  const attachResource = (resourceId: string) => {
    if (!project) return;
    window.dispatchEvent(new CustomEvent('va-attach-resource', { detail: { projectId: project.id, resourceId } }));
    navigate('overview');
  };
  const sourceReturnLabel = `Back to ${destinations.find(([id]) => id === sourceReturn)?.[1] ?? 'Resources'}`;
  const activeJobs = project?.jobs.filter(job => ['queued', 'running'].includes(job.status) && (!job.parent_job_id || !project.jobs.some(parent => parent.id === job.parent_job_id))) ?? [];
  return <div className="va-app"><a className="va-skip-link" href={project ? "#va-workspace-main" : "#va-library-main"}>Skip to workspace</a><header className="va-topbar"><Brand />{project && <div className="va-project-heading"><strong>{project.title}</strong><span className="va-save-state" role="status">{error ? 'Action needs attention' : saving ? 'Saving…' : <><Icon name="check" size={15} />Saved locally</>}</span></div>}<div className="va-topbar-actions">{project && <button ref={activityToggle} type="button" className="va-activity-toggle" aria-expanded={activity} aria-controls="va-activity-panel" onClick={() => activity ? closeActivity() : setActivity(true)}>{activeJobs.length ? <span className="va-spinner" /> : <Icon name="analysis" size={17} />}Activity{activeJobs.length > 0 && <Badge>{activeJobs.length}</Badge>}</button>}<button className="va-icon-button" aria-label="Settings" onClick={() => setSettings(value => !value)}><Icon name="settings" /></button><span className="va-avatar">VA</span></div></header>
    {error && <div className="va-global-error" role="alert"><span>{failureMessage(error)}</span><ConnectionHelp message={error} /><button className="va-icon-button" aria-label="Dismiss error" onClick={() => controller.setError('')}><Icon name="close" size={17} /></button></div>}
    {migrationErrors.map((message, index) => <div className="va-global-error" role="alert" key={index}><span>{message}</span><a href="?legacy=1">Open preserved legacy workspace</a></div>)}
    {settings && <section className="va-settings va-glass"><h2>Settings</h2><p>Version {build.version}<br />Source commit: <code>{build.source_commit ?? 'Unavailable in this installation'}</code></p><ApiConnectionButton /><p>Language and vision: <strong>gpt-6.1-sol</strong><br />Speech transcription: <strong>Whisper or GPT Transcribe</strong><br />Choose the speech model in Resources or Source Review. GPT Transcribe uses audio-chunk timing; Whisper provides estimated segment timing.</p><p>Your key is stored locally. Selected context and media are sent to the configured provider for requested processing. Model access is checked when requested.</p>{project && <button onClick={() => { if (window.confirm('Clear rebuildable thumbnails, previews, and prepared media? Originals, transcripts, corrections, and saved work will remain.')) void mutate('/cache/clear'); }}>Clear derived cache</button>}<a href="?legacy=1">Open preserved legacy workspace</a><button onClick={() => setSettings(false)}>Close settings</button></section>}
    {!project ? <Dashboard projects={controller.projects} loading={controller.loading} onOpen={controller.open} onRefresh={controller.refreshList} onError={controller.setError} /> : <div className="va-workspace" key={project.id}><aside className="va-rail"><button className="va-all-projects" onClick={() => void controller.close()}><Icon name="back" />All projects</button><h2 className="va-rail-title">{project.title}</h2><details className="va-project-navigation" open><summary>Project navigation</summary><nav aria-label="Project destinations">{destinations.map(([id, label]) => <button key={id} className={area === id ? 'active' : ''} aria-current={area === id ? 'page' : undefined} onClick={() => navigate(id)}><Icon name={id} />{label}</button>)}</nav></details><div className="va-rail-bottom"><ApiConnectionButton /><span>{project.resources.length} local resources</span></div></aside><main id="va-workspace-main" className="va-workspace-main" tabIndex={-1}>
      <div hidden={area !== 'overview'}><Overview project={project} mutate={mutate} onSource={onSource} /></div>
      <div hidden={area !== 'resources'}><Resources project={project} mutate={mutate} source={sourceProject.current === project.id ? source : null} onAnalyze={() => navigate('analysis')} onCloseSource={closeSource} sourceReturnLabel={sourceReturnLabel} onAttachResource={attachResource} /></div>
      <div hidden={area !== 'discover'} className="va-discovery"><h1>Discover</h1><p className="va-muted">Reserved — awaiting Frank’s specification.</p><section className="va-glass va-discovery-placeholder"><Icon name="discover" size={36} /><h2>Bring your own references</h2><p>Discovery is not available yet. Upload local files in Resources to start exploring their evidence.</p><button className="va-primary" onClick={() => navigate('resources')}><Icon name="upload" />Open Resources</button></section></div>
      <div hidden={area !== 'analysis'}><AnalysisView project={project} mutate={mutate} onSource={onSource} onResources={() => navigate('resources')} onContent={() => navigate('content')} /></div>
      <div hidden={area !== 'content'}><ContentPlan project={project} mutate={mutate} onOverview={() => navigate('overview')} onSource={onSource} onProduction={() => navigate('production')} /></div>
      <div hidden={area !== 'production'}><ProductionView project={project} mutate={mutate} onSource={onSource} onContent={() => navigate('content')} /></div>
    </main>{activity && <ActivityPanel project={project} mutate={mutate} version={build.version} sourceCommit={build.source_commit} onClose={closeActivity} onSource={(resourceId, revision) => { setActivity(false); onSource({ resource_id: resourceId, message_id: null, locator: '', excerpt: '', url: null, evidence_revision: revision, extraction_revision: null, event_id: null, start_seconds: null, end_seconds: null }); }} />}</div>}
  </div>;
}

export default function ProjectApp() { return <ApiConnection><Application /></ApiConnection>; }
