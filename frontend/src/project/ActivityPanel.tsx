import { useRef, useState } from 'react';
import type { Job, Project } from './contracts';
import { Badge, Icon, SupportDetails, date } from './Common';
import type { Mutate } from './client';
import { failureMessage, jobLabel, jobStatus } from './status';
import { resourceIsTrashed } from './resourceLibrary';
import './activity.css';

const active = (job: Job) => ['queued', 'running'].includes(job.status);

export function ReportRetry({ project, job, mutate }: { project: Project; job: Job; mutate: Mutate }) {
  const [pending, setPending] = useState(false);
  const [receipt, setReceipt] = useState('');
  const ids = job.resource_ids ?? [];
  const resources = ids.map(id => project.resources.find(item => item.id === id));
  const blocked = pending || project.jobs.some(item => item.kind === 'analyze' && item.content_id === job.content_id && active(item));
  const available = ids.length > 0 && resources.every(item => item && !resourceIsTrashed(project, item)) && resources.some(item => item?.evidence.some(evidence => evidence.events.length));
  const content = project.contents.find(item => item.id === job.content_id);
  const currentSelection = content?.selection.resource_ids ?? project.selection.resource_ids;
  const sameScope = currentSelection.length === ids.length && currentSelection.every((id, index) => id === ids[index]);
  const retry = async () => {
    if (blocked || !available || !sameScope) return;
    setPending(true);
    try {
      const saved = await mutate('/analyze', { resource_ids: ids, content_id: job.content_id, synthesis_only: true, visual_only: job.diagnostics.visual_only === 'true' });
      if (saved) setReceipt('Report synthesis started. Saved source evidence is reused; recognition was not restarted.');
    } finally { setPending(false); }
  };
  return <div className="va-report-retry"><button type="button" disabled={blocked || !available || !sameScope || Boolean(content?.trashed_at)} onClick={() => void retry()}>{pending ? 'Starting synthesis…' : 'Retry report synthesis'}</button><p className="va-muted">{!available ? 'Choose available references in Resources to start a new report. This task has no complete saved request scope.' : !sameScope ? 'The reference selection changed. Choose references in Resources to start a new report; retry will not restore an old selection.' : content?.trashed_at ? 'Restore this Video in Content plan before retrying.' : 'Reuses this task’s saved references. It does not repeat visual or speech recognition.'}</p>{receipt && <p role="status">{receipt}</p>}</div>;
}

export default function ActivityPanel({ project, mutate, version, sourceCommit, onClose, onSource }: { project: Project; mutate: Mutate; version: string; sourceCommit: string | null; onClose: () => void; onSource: (resourceId: string, revision: number | null) => void }) {
  const [all, setAll] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const jobIds = new Set(project.jobs.map(job => job.id));
  const roots = project.jobs.filter(job => !job.parent_job_id || !jobIds.has(job.parent_job_id)).slice().reverse();
  const task = (job: Job, child = false) => {
    const resource = project.resources.find(item => item.id === job.resource_id);
    const revision = Number(job.diagnostics.evidence_revision) || null;
    const evidence = resource?.evidence.find(item => item.revision === revision);
    const incomplete = evidence ? Object.entries(evidence.coverage).filter(([, value]) => ['failed', 'partial', 'error'].includes(value)).map(([channel]) => channel === 'visual_action' ? 'Visual' : channel === 'on_screen_text' ? 'On-screen text' : channel[0].toUpperCase() + channel.slice(1)) : [];
    const source = project.resources.find(item => item.id === job.diagnostics.resource_id);
    const children = project.jobs.filter(item => item.parent_job_id === job.id);
    const report = job.kind === 'analyze';
    const hasOldReport = project.analyses.some(item => item.content_id === job.content_id);
    const title = resource ? resource.name : report ? 'Reference analysis' : jobLabel[job.kind] ?? 'Project processing';
    const status = report && job.status === 'partial' ? 'Report saved · source limits' : jobStatus[job.status] ?? 'Needs attention';
    const diagnostics = [{ ...job.diagnostics, application_version: job.diagnostics.application_version || version, source_commit: job.diagnostics.source_commit || sourceCommit || 'unavailable', project_id: project.id, job_id: job.id, parent_job_id: job.parent_job_id ?? '', status: job.status, failure_code: job.error_code ?? '' }, ...(job.support_details ?? [])];
    return <article key={job.id} className={child ? 'va-activity-child' : 'va-activity-operation'} aria-label={`${title} ${status}`}>
      <div className="va-activity-task-heading"><strong>{title}</strong><Badge tone={['failed', 'partial'].includes(job.status) ? 'warning' : ''}>{status}</Badge></div>
      <p>{job.progress || (active(job) ? 'Waiting for processing details…' : status)}{active(job) && source ? ` · ${source.name}` : ''}</p>
      {active(job) && <progress aria-label={`${title} progress`} />}
      {active(job) && job.diagnostics.source_index && <p className="va-muted">Reference {job.diagnostics.source_index} of {job.diagnostics.source_total}</p>}
      {report && job.resource_ids?.length > 0 && <details><summary>{job.resource_ids.length} selected references · {project.contents.find(item => item.id === job.content_id)?.title ?? 'Project exploration'}</summary><ul>{job.resource_ids.map(id => <li key={id}>{project.resources.find(item => item.id === id)?.name ?? 'Unavailable source'}</li>)}</ul></details>}
      {job.status === 'partial' && <p>{report ? 'The report is saved. Review its source coverage before using audio-dependent conclusions.' : incomplete.length ? `${incomplete.join(', ')} incomplete. Other valid source observations were saved.` : 'Source evidence was saved with limitations. Open its coverage and processing details.'}</p>}
      {job.error && <p className="va-activity-error">{failureMessage(job.error, job.error_code)}</p>}
      {report && job.status === 'failed' && <><p>{hasOldReport ? 'The earlier report remains saved. This attempt did not replace it.' : 'This attempt did not save a report.'} Saved source evidence is retained.</p><ReportRetry project={project} job={job} mutate={mutate} /></>}
      {resource && <button type="button" onClick={() => onSource(resource.id, revision)}>{revision ? `Open saved evidence v${revision}` : 'Open current source'} · {resource.name}</button>}
      {children.length > 0 && <details open={active(job) || ['failed', 'partial'].includes(job.status)}><summary>Source recognition · {children.filter(item => !active(item)).length} of {children.length} finished</summary><div>{children.map(item => task(item, true))}</div></details>}
      <small className="va-muted">{date(job.created_at)} · {job.kind === 'reference_extraction' ? 'Source evidence' : jobLabel[job.kind] ?? 'Project task'}</small>
      <SupportDetails diagnostics={diagnostics} label="Processing details" />
    </article>;
  };
  return <aside id="va-activity-panel" className="va-activity va-glass va-activity-184" aria-labelledby="va-activity-title"><div className="va-section-heading"><h2 id="va-activity-title" ref={heading} tabIndex={-1}>Activity</h2><button type="button" aria-label="Close activity" className="va-icon-button" onClick={onClose}><Icon name="close" /></button></div><p className="va-muted">Source evidence and final reports are saved in separate steps.</p>{!roots.length && <p>No processing yet.</p>}{(all ? roots : roots.slice(0, 20)).map(job => task(job))}{!all && roots.length > 20 && <button type="button" onClick={() => setAll(true)}>Show earlier tasks</button>}</aside>;
}
