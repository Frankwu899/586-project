import { useEffect, useRef, useState, type FormEvent } from 'react';
import type { TaskState } from './generated/contracts';
import { registerTranslations, useI18n } from './i18n';
import { Field } from './ui';

registerTranslations({
  'Saved tasks': '已保存的项目', 'Projects': '项目', 'Trash': '废纸篓',
  'New task title': '新项目名称', 'Project name': '项目名称', 'New project': '新建项目',
  'Create task': '创建项目', 'Restoring projects…': '正在恢复项目…',
  'Close project': '关闭项目', 'Open project': '打开项目', 'Rename project': '重命名项目',
  'Project actions for {title}': '{title}的项目菜单', 'Move to Trash': '移到废纸篓',
  'Restore project': '恢复项目', 'Trash is empty.': '废纸篓为空。',
  'No projects yet.': '尚无项目。', 'Processing…': '处理中…',
  'Project commands are available after the current operation finishes.': '当前操作结束后即可使用项目菜单。',
  'Move “{title}” to Trash?': '将“{title}”移到废纸篓？',
  'The project, drafts, and imported media are kept. You can restore them from Trash.': '项目、草稿和已导入媒体都会保留，可从废纸篓恢复。',
  'Saving…': '保存中…', 'Rename': '重命名',
  'Projects and imported files stay on this computer.': '项目和已导入文件保存在此电脑。',
  'Reopen saved task': '重新打开已保存项目',
  'Production saved': '制作内容已保存', 'Idea approved': '创意已批准',
  'Ideas saved': '创意已保存', 'Research saved': '研究已保存', 'Video imported': '视频已导入',
  'Could not update project.': '无法更新项目。',
});

type Props = {
  tasks: TaskState[]; trashed: TaskState[]; active: TaskState | null;
  title: string; onTitle: (title: string) => void; loading: boolean; navigating: boolean;
  error: string; busyIds: Set<string>;
  onOpen: (id: string) => Promise<void>; onClose: () => Promise<void>;
  onCreate: (event: FormEvent) => void; onLoadTrash: () => Promise<void>;
  onRename: (id: string, title: string) => Promise<void>;
  onTrash: (id: string) => Promise<void>; onRestore: (id: string) => Promise<void>;
};

function progress(state: TaskState) {
  if (state.task.current_production_brief) return 'Production saved';
  if (state.task.selected_direction) return 'Idea approved';
  if (state.directions.length) return 'Ideas saved';
  if (state.task.current_analysis) return 'Research saved';
  return state.task.current_video_id ? 'Video imported' : 'New project';
}

export default function ProjectSidebar(props: Props) {
  const { t } = useI18n();
  const [view, setView] = useState<'projects' | 'trash'>('projects');
  const [command, setCommand] = useState<{ kind: 'rename' | 'trash'; task: TaskState } | null>(null);
  const [rename, setRename] = useState('');
  const [dialogError, setDialogError] = useState('');
  const [pending, setPending] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    if (command) dialog.current?.showModal();
    else dialog.current?.close();
  }, [command]);
  const openCommand = (kind: 'rename' | 'trash', task: TaskState, button: HTMLButtonElement) => {
    const menu = button.closest('details'); if (menu) menu.open = false;
    setDialogError(''); setRename(task.task.title); setCommand({ kind, task });
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault(); if (!command || pending) return;
    setPending(true); setDialogError('');
    try {
      if (command.kind === 'rename') await props.onRename(command.task.task.task_id, rename.trim());
      else await props.onTrash(command.task.task.task_id);
      setCommand(null);
    } catch (failure) { setDialogError(failure instanceof Error ? failure.message : t('Could not update project.')); }
    finally { setPending(false); }
  };
  const tasks = view === 'projects' ? props.tasks : props.trashed;
  return <aside id="project-sidebar" className="task-sidebar" aria-label={t('Saved tasks')}>
    <div className="sidebar-heading"><h2>{t('Projects')}</h2><span>{props.tasks.length}</span></div>
    <form onSubmit={(event) => { setView('projects'); props.onCreate(event); }}><Field label={t('New task title')}><input required placeholder={t('Project name')} value={props.title} onChange={(event) => props.onTitle(event.target.value)} disabled={props.navigating || props.loading} /></Field><button type="submit" aria-label={t('Create task')} disabled={props.navigating || props.loading || !props.title.trim()}>{t('New project')}</button></form>
    <nav className="sidebar-views" aria-label={t('Projects')}><button type="button" className="text-button" aria-current={view === 'projects' ? 'page' : undefined} onClick={() => setView('projects')}>{t('Projects')}</button><button type="button" className="text-button" aria-current={view === 'trash' ? 'page' : undefined} onClick={() => { setView('trash'); void props.onLoadTrash(); }}>{t('Trash')}</button></nav>
    {props.error && <p role="alert" className="error sidebar-error">{t(props.error)}</p>}
    {props.loading ? <p role="status" className="muted">{t('Restoring projects…')}</p> : <ul className="task-list">{tasks.map((item) => {
      const id = item.task.task_id; const busy = props.busyIds.has(id);
      return <li key={id} className={`project-row${view === 'trash' ? ' project-trashed' : ''}`}>
        {view === 'trash' ? <><div className="project-open"><strong>{item.task.title}</strong></div><button type="button" className="secondary" disabled={props.navigating} onClick={() => { void props.onRestore(id).then(() => setView('projects')).catch(() => { /* The sidebar retains the error. */ }); }}>{t('Restore project')}</button></> : <>
          <button type="button" className="project-open" aria-current={props.active?.task.task_id === id ? 'page' : undefined} onClick={() => { void props.onOpen(id); }} disabled={props.navigating}><strong>{item.task.title}</strong><small>{t(busy ? 'Processing…' : progress(item))}</small></button>
          <details className="project-actions"><summary aria-label={t('Project actions for {title}', { title: item.task.title })}>•••</summary><div className="project-action-menu"><button type="button" onClick={(event) => { const menu = event.currentTarget.closest('details'); if (menu) menu.open = false; void props.onOpen(id); }} disabled={props.navigating}>{t('Open project')}</button><button type="button" disabled={props.navigating || busy} onClick={(event) => openCommand('rename', item, event.currentTarget)}>{t('Rename project')}</button><button type="button" className="danger" disabled={props.navigating || busy} onClick={(event) => openCommand('trash', item, event.currentTarget)}>{t('Move to Trash')}</button>{busy && <small>{t('Project commands are available after the current operation finishes.')}</small>}</div></details>
        </>}
      </li>;
    })}</ul>}
    {!props.loading && !tasks.length && <p className="muted">{t(view === 'trash' ? 'Trash is empty.' : 'No projects yet.')}</p>}
    <div className="sidebar-bottom">{props.active && <><button type="button" className="secondary close-project" disabled={props.navigating || props.busyIds.has(props.active.task.task_id)} onClick={() => { void props.onClose(); }}>{t('Close project')}</button><button type="button" className="text-button reopen-task" disabled={props.navigating} onClick={() => { void props.onOpen(props.active!.task.task_id); }}>{t('Reopen saved task')}</button></>}<p className="sidebar-note">{t('Projects and imported files stay on this computer.')}</p></div>
    <dialog ref={dialog} className="project-dialog" aria-labelledby="project-command-title" onCancel={(event) => { event.preventDefault(); if (!pending) setCommand(null); }}>
      {command && <form onSubmit={(event) => { void submit(event); }}><h2 id="project-command-title">{command.kind === 'rename' ? t('Rename project') : t('Move “{title}” to Trash?', { title: command.task.task.title })}</h2>{command.kind === 'rename' ? <Field label={t('Project name')}><input autoFocus required value={rename} onChange={(event) => setRename(event.target.value)} disabled={pending} /></Field> : <p>{t('The project, drafts, and imported media are kept. You can restore them from Trash.')}</p>}{dialogError && <p className="error project-dialog-error" role="alert">{t(dialogError)}</p>}<div className="project-dialog-actions"><button type="button" className="secondary" disabled={pending} onClick={() => setCommand(null)}>{t('Cancel')}</button><button type="submit" disabled={pending || (command.kind === 'rename' && !rename.trim())}>{pending ? t('Saving…') : command.kind === 'rename' ? t('Rename') : t('Move to Trash')}</button></div></form>}
    </dialog>
  </aside>;
}
