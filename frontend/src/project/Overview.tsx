import { useEffect, useRef, useState } from 'react';
import type { Fact, Job, Project } from './contracts';
import { FailureNotice, SupportDetails, Badge, DraftConflict, Icon, Sources, type SourceAction } from './Common';
import { useDraft, type Mutate } from './client';
import { isClaimKey } from './status';
import './overview.css';

const label = (key: string) => key.replaceAll('_', ' ');
const sameInformation = (a: Fact, b: Fact) => a.key === b.key && a.value === b.value && a.permitted_for_use === b.permitted_for_use;
const includeCurrent = (draft: Fact[], current: Fact[]) => [...draft, ...current.filter(fact => !draft.some(item => item.id === fact.id))];
const activeReply = (project: Project, messageId?: string) => project.jobs.slice().reverse().find(job => job.kind === 'conversation' && ['queued', 'running'].includes(job.status) && (!messageId || job.message_id === messageId));

function BriefSnapshot({ project, changes, onReview }: { project: Project; changes: number; onReview: () => void }) {
  const current = project.briefs.at(-1);
  const groups = [
    { title: 'Brand / product', matches: /brand|product|company|品牌|产品|公司/i },
    { title: 'Audience', matches: /audience|customer|人群|受众/i },
    { title: 'Goal', matches: /objective|goal|assignment|目的|目标|任务/i },
    { title: 'Platform / duration', matches: /platform|duration|format|channel|平台|时长|格式/i },
    { title: 'Claims / constraints', matches: /claim|benefit|constraint|restriction|主张|功效|限制|约束/i },
  ];
  const assigned = new Set<string>();
  const rows = groups.map(group => {
    const facts = current?.facts.filter(fact => !assigned.has(fact.id) && (isClaimKey(fact.key) ? group.title === 'Claims / constraints' : group.matches.test(fact.key))) ?? [];
    facts.forEach(fact => assigned.add(fact.id));
    return { ...group, facts };
  }).filter(group => group.facts.length);
  const other = current?.facts.filter(fact => !assigned.has(fact.id)) ?? [];
  return <section className="va-glass va-brief va-brief-snapshot" aria-label="Current project brief">
    <div className="va-section-heading"><h2>Project brief</h2><Badge tone={current?.facts.length ? 'success' : ''}>{current?.facts.length ? `In use · v${current.revision}` : 'Not yet applied'}</Badge></div>
    {current?.facts.length ? <><p className="va-muted">The confirmed context in use for your creative work.</p><dl className="va-brief-summary">{rows.map(group => <div key={group.title}><dt>{group.title}</dt><dd>{group.facts.map(fact => <p key={fact.id}>{fact.value}</p>)}</dd></div>)}</dl>{other.length > 0 && <details className="va-brief-more"><summary>Other confirmed context ({other.length})</summary><dl className="va-brief-summary">{other.map(fact => <div key={fact.id}><dt>{label(fact.key)}</dt><dd>{fact.value}</dd></div>)}</dl></details>}</> : <p className="va-brief-empty">No brief is in use yet. Describe your task in the conversation, then review the proposed information before applying it.</p>}
    {project.unresolved.length > 0 && <p className="va-brief-gap"><strong>Needs confirmation</strong> {project.unresolved[0]}</p>}
    <button type="button" className={changes ? 'va-primary va-full-width' : 'va-full-width'} onClick={onReview} aria-haspopup="dialog">{changes ? `Review changes (${changes})` : 'Review brief'}</button>
    {changes > 0 && <small className="va-muted">Proposed information is separate from the brief in use.</small>}
  </section>;
}

export default function Overview({ project, mutate, onSource }: { project: Project; mutate: Mutate; onSource: SourceAction }) {
  const [composer, setComposer, flushComposer, composerConflict, reloadComposer] = useDraft(project, 'conversation', { text: project.conversation_draft, resource_ids: [] as string[] }, mutate);
  const [sending, setSending] = useState(false);
  const [retrying, setRetrying] = useState<string | null>(null);
  const [stopping, setStopping] = useState(false);
  const stopRequested = useRef(false);
  const conversationJob = activeReply(project);
  const conversationBusy = sending || retrying !== null || Boolean(conversationJob);
  const [uploading, setUploading] = useState(false);
  const composerRef = useRef(composer);
  composerRef.current = composer;
  const attachment = useRef<HTMLInputElement>(null);
  const messages = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  const composing = useRef(false);
  const reviewDialog = useRef<HTMLDialogElement>(null);
  const snapshotDialog = useRef<HTMLDialogElement>(null);
  const [editing, setEditing] = useState<Fact | null>(null);
  const [adding, setAdding] = useState(false);
  const [factKey, setFactKey] = useState('');
  const [factValue, setFactValue] = useState('');
  const [claimRemovals, setClaimRemovals] = useState<string[]>([]);
  const currentBrief = project.briefs.at(-1);
  const currentFacts = currentBrief?.facts ?? [];
  const recoveryKey = `video-anatomy:1.8:${project.id}:brief-recovery`;
  const [recovered] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(recoveryKey) ?? 'null') as { facts: Fact[]; base_version: number } | null;
      if (stored && Array.isArray(stored.facts) && typeof stored.base_version === 'number' && JSON.stringify(stored.facts) !== JSON.stringify(project.brief_draft)) return stored;
    } catch { /* The saved project remains authoritative. */ }
    return null;
  });
  const [facts, setFacts] = useState(includeCurrent(recovered?.facts ?? project.brief_draft, currentFacts));
  const [factSaving, setFactSaving] = useState(false);
  const [factFailed, setFactFailed] = useState(Boolean(recovered));
  const factVersion = useRef(recovered?.base_version ?? project.brief_draft_version);
  useEffect(() => {
    if (!factSaving && !factFailed && !editing && !adding) { setFacts(includeCurrent(project.brief_draft, project.briefs.at(-1)?.facts ?? [])); factVersion.current = project.brief_draft_version; }
  }, [project.brief_draft, project.brief_draft_version, project.briefs, factSaving, factFailed, editing, adding]);
  useEffect(() => {
    if (following.current && messages.current) messages.current.scrollTop = messages.current.scrollHeight;
  }, [project.messages.length, conversationBusy]);
  const persistFacts = async (next: Fact[]) => {
    setFacts(next); setFactSaving(true);
    try { localStorage.setItem(recoveryKey, JSON.stringify({ facts: next, base_version: factVersion.current })); } catch { /* The project save still runs. */ }
    const saved = await mutate('/brief/draft', { expected_draft_version: factVersion.current, facts: next });
    if (saved) {
      setFacts(includeCurrent(saved.brief_draft, saved.briefs.at(-1)?.facts ?? [])); factVersion.current = saved.brief_draft_version; setFactFailed(false);
      try { localStorage.removeItem(recoveryKey); } catch { /* A successful project save is authoritative. */ }
    } else setFactFailed(true);
    setFactSaving(false); return saved;
  };
  const updateFact = (fact: Fact, changes: Partial<Fact>) => persistFacts(facts.map(item => item.id === fact.id ? { ...item, ...changes } : item));
  const keepCurrent = async (fact: Fact, current: Fact) => {
    const saved = await updateFact(fact, current);
    // Restoring text clears permission on the server just like any edit. Restore
    // only this already-adopted permission in a second version-checked save.
    const restored = saved?.brief_draft.find(item => item.id === current.id);
    if (saved && restored && !sameInformation(restored, current)) await persistFacts(saved.brief_draft.map(item => item.id === current.id ? current : item));
  };
  const stopAttempt = async (job: Job | undefined) => {
    if (!job?.message_id || !job.attempt_id) return;
    await mutate(`/messages/${job.message_id}/stop`, { attempt_id: job.attempt_id });
  };
  const stop = async () => {
    if (stopping) return;
    stopRequested.current = true; setStopping(true);
    if (sending || retrying !== null) return;
    try { await stopAttempt(conversationJob); } finally { setStopping(false); stopRequested.current = false; }
  };
  const retry = async (messageId: string) => {
    if (conversationBusy) return;
    stopRequested.current = false; setRetrying(messageId);
    try {
      const saved = await mutate(`/messages/${messageId}/retry`);
      if (saved && stopRequested.current) await stopAttempt(activeReply(saved, messageId));
    } finally { setRetrying(null); setStopping(false); stopRequested.current = false; }
  };
  const send = async () => {
    if (!composer.text.trim() || conversationBusy || uploading || composing.current) return;
    stopRequested.current = false; setSending(true);
    try {
      if (!await flushComposer()) return;
      if (stopRequested.current) return; // No message/attempt was admitted; retain this draft and its attachments.
      const saved = await mutate('/messages', { text: composer.text, resource_ids: composer.resource_ids });
      if (saved) {
        setComposer({ text: '', resource_ids: [] });
        if (stopRequested.current) await stopAttempt(activeReply(saved));
        void mutate('', { conversation_draft: '' }, 'PATCH');
      }
    } finally { setSending(false); setStopping(false); stopRequested.current = false; }
  };
  const upload = async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    const ids: string[] = [];
    try {
      for (const file of Array.from(files)) {
        const data = new FormData(); data.append('file', file); data.append('role', 'document');
        const saved = await mutate('/resources', data);
        if (saved) { const added = saved.resources.at(-1); if (added) ids.push(added.id); }
      }
      setComposer({ ...composerRef.current, resource_ids: [...new Set([...composerRef.current.resource_ids, ...ids])] });
    } finally { setUploading(false); }
  };
  const saveCorrection = async () => {
    if (!factKey.trim() || !factValue.trim()) return;
    const changed: Fact = editing
      ? { ...editing, key: factKey.trim(), value: factValue.trim(), status: 'suggested', permitted_for_use: false }
      : { id: `fact_${crypto.randomUUID().replaceAll('-', '')}`, key: factKey.trim(), value: factValue.trim(), status: 'suggested', origin: 'manual', sources: [], permitted_for_use: false };
    const result = await persistFacts(editing ? facts.map(item => item.id === editing.id ? changed : item) : [...facts, changed]);
    if (result) { setEditing(null); setAdding(false); }
  };
  const changedFacts = facts.filter(fact => {
    const current = currentFacts.find(item => item.id === fact.id);
    return current ? fact.status === 'rejected' || !sameInformation(fact, current) : fact.status !== 'rejected';
  });
  const selectedChanges = changedFacts.filter(fact => fact.status === 'confirmed' || (fact.status === 'rejected' && currentFacts.some(item => item.id === fact.id)));
  const missingClaimPermission = selectedChanges.some(fact => fact.status === 'confirmed' && isClaimKey(fact.key) && !fact.permitted_for_use);
  const unconfirmedRemoval = selectedChanges.some(fact => fact.status === 'rejected' && isClaimKey(fact.key) && !claimRemovals.includes(fact.id));
  const canApply = !factSaving && !factFailed && selectedChanges.length > 0 && !missingClaimPermission && !unconfirmedRemoval;
  const openReview = () => { snapshotDialog.current?.close(); reviewDialog.current?.showModal(); };
  const apply = async () => {
    if (!canApply) return;
    setFactSaving(true);
    try {
      const saved = await mutate('/brief/apply', { expected_draft_version: factVersion.current, facts });
      if (saved) { setClaimRemovals([]); reviewDialog.current?.close(); }
    } finally { setFactSaving(false); }
  };
  const edit = (fact: Fact) => { setEditing(fact); setAdding(false); setFactKey(fact.key); setFactValue(fact.value); };
  const recoveryNotice = factFailed && <div className="va-notice" role="alert">Your proposed changes are retained on this computer but are not saved to the project.<button type="button" disabled={factSaving} onClick={() => void persistFacts(facts)}>Retry draft save</button><button type="button" disabled={factSaving} onClick={() => {
    if (window.confirm('Replace your retained changes with the current saved brief draft?')) {
      setFacts(includeCurrent(project.brief_draft, currentFacts)); factVersion.current = project.brief_draft_version; setFactFailed(false);
      try { localStorage.removeItem(recoveryKey); } catch { /* Saved project remains authoritative. */ }
    }
  }}>Reload saved draft</button></div>;

  return <div className="va-overview-frame"><div className="va-overview">
    <section className="va-conversation va-glass" aria-label="Project conversation">
      <div className="va-conversation-heading"><div><span className="va-eyebrow">OVERVIEW</span><h1>{project.messages.length ? 'Describe the video you want to make.' : 'What do you want to create today?'}</h1></div><button type="button" className="va-view-brief" onClick={() => snapshotDialog.current?.showModal()} aria-haspopup="dialog"><Icon name="file" size={17} />View brief{changedFacts.length > 0 && <Badge>{changedFacts.length}</Badge>}</button></div>
      <div className="va-messages" ref={messages} role="log" aria-label="Conversation" aria-live="polite" onScroll={() => { const node = messages.current; if (node) following.current = node.scrollHeight - node.scrollTop - node.clientHeight < 70; }}>
        {!project.messages.length && <div className="va-conversation-welcome"><Icon name="spark" size={35} /><p>Describe the task, paste notes, or attach a brief. Start with what you know.</p><div className="va-prompt-hints"><span>Develop a video idea</span><span>Understand references</span></div></div>}
        {project.messages.map(message => {
          const turn = message.reply_to_message_id;
          const latestForTurn = !turn || (project.messages.filter(item => item.reply_to_message_id === turn).at(-1)?.id === message.id && project.messages.filter(item => item.role === 'user').at(-1)?.id === turn);
          const diagnostics = { ...message.diagnostics, project_id: project.id, message_id: message.id, conversation_turn_id: turn ?? message.id };
          const recoverable = message.status === 'failed' || message.status === 'stopped';
          return <article id={`conversation-${message.id}`} key={message.id} className={`va-message ${message.role}`}><div className="va-message-avatar">{message.role === 'assistant' ? <Icon name="spark" /> : 'You'}</div><div className="va-message-body">
            {message.status === 'failed' ? <FailureNotice message={message.text} code={message.diagnostics?.failure_code ?? message.diagnostics?.error_code} diagnostics={diagnostics} /> : <><p>{message.text}</p>{message.role === 'assistant' && message.status !== 'stopped' && <SupportDetails diagnostics={diagnostics} />}</>}
            {message.resource_ids.length > 0 && <div className="va-sources">{message.resource_ids.map(id => <button type="button" key={id} onClick={() => onSource({ resource_id: id, message_id: null, locator: '', excerpt: '', url: null, evidence_revision: null, extraction_revision: null, event_id: null, start_seconds: null, end_seconds: null })}><Icon name="file" size={14} />{project.resources.find(resource => resource.id === id)?.name ?? 'Attachment'}</button>)}</div>}
            {recoverable && <div className="va-message-recovery">{message.status === 'failed' && <Badge tone="warning">{latestForTurn ? 'Assistance incomplete · message saved' : 'Earlier attempt · retained for reference'}</Badge>}{message.retryable && turn && latestForTurn && <button type="button" disabled={conversationBusy} onClick={() => void retry(turn)}>{retrying === turn || conversationJob?.message_id === turn ? 'Retrying…' : 'Retry assistance'}</button>}</div>}
          </div></article>;
        })}
        {conversationBusy && <p className="va-assistant-working" role="status"><span className="va-spinner" />{stopping ? 'Stopping this response…' : sending ? 'Saving your message…' : conversationJob?.status === 'queued' ? 'Your message is saved. Waiting to start…' : 'Preparing a reply… Your message is saved.'}</p>}
      </div>
      <DraftConflict conflict={composerConflict} reload={reloadComposer} />
      <form className="va-composer" onSubmit={event => { event.preventDefault(); void send(); }}>
        <div className="va-attachment-row">{composer.resource_ids.map(id => { const resource = project.resources.find(item => item.id === id); return <span key={id}><Icon name="file" size={15} /><span>{resource?.name ?? 'Attachment'}</span><Badge>{resource?.status ?? 'Saved'}</Badge><button type="button" aria-label={`Detach ${resource?.name ?? 'file'}`} onClick={() => setComposer({ ...composer, resource_ids: composer.resource_ids.filter(value => value !== id) })}>×</button></span>; })}</div>
        <label className="va-sr-only" htmlFor={`message-${project.id}`}>Describe your assignment</label>
        <textarea id={`message-${project.id}`} placeholder="Message Video Anatomy…" value={composer.text} disabled={sending} onChange={event => setComposer({ ...composer, text: event.target.value })} onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }} onBlur={() => { void mutate('', { conversation_draft: composer.text }, 'PATCH'); }} onKeyDown={event => {
          if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
            if (composing.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return;
            event.preventDefault(); event.currentTarget.form?.requestSubmit();
          }
        }} />
        <div className="va-composer-footer"><input ref={attachment} type="file" tabIndex={-1} className="va-sr-only" multiple onChange={event => { void upload(event.target.files); event.target.value = ''; }} /><button type="button" className="va-icon-button" aria-label="Attach documents" disabled={conversationBusy || uploading} onClick={() => attachment.current?.click()}><Icon name="plus" /></button><span>{uploading ? 'Saving attachments…' : '⌘ / Ctrl + Enter to send'}</span>
          {conversationBusy ? <button type="button" className="va-primary va-send va-stop" aria-label="Stop response" disabled={stopping || (!sending && retrying === null && !conversationJob?.attempt_id)} onClick={() => void stop()}><span className="va-stop-symbol" aria-hidden="true" />{stopping ? 'Stopping…' : 'Stop response'}</button> : <button type="submit" className="va-primary va-send" disabled={!composer.text.trim() || uploading} aria-label="Send message"><Icon name="send" size={18} />Send</button>}
        </div>
      </form>
    </section>
    <aside className="va-overview-inspector"><BriefSnapshot project={project} changes={changedFacts.length} onReview={openReview} />{factFailed && <button type="button" className="va-notice" onClick={openReview}>Your retained brief changes need review.</button>}</aside>
  </div>
  <dialog ref={snapshotDialog} className="va-brief-dialog va-brief-view-dialog" aria-labelledby={`brief-title-${project.id}`}><div className="va-review-heading"><h2 id={`brief-title-${project.id}`}>Current brief</h2><button type="button" autoFocus className="va-icon-button" aria-label="Close brief" onClick={() => snapshotDialog.current?.close()}><Icon name="close" /></button></div><BriefSnapshot project={project} changes={changedFacts.length} onReview={openReview} /></dialog>
  <dialog ref={reviewDialog} className="va-brief-dialog va-brief-review-dialog" aria-labelledby={`review-title-${project.id}`}>
    <div className="va-review-heading"><div><h2 id={`review-title-${project.id}`}>Review brief changes</h2><p>Only Apply updates changes the brief in use.</p></div><button type="button" autoFocus className="va-icon-button" aria-label="Close review" onClick={() => reviewDialog.current?.close()}><Icon name="close" /></button></div>
    {recoveryNotice}{factSaving && <p className="va-muted" role="status">Saving proposed information…</p>}
    <div className="va-review-changes">{!changedFacts.length && <p className="va-brief-empty">No proposed changes. Use the conversation to correct the brief, or add information here.</p>}{changedFacts.map(fact => {
      const current = currentFacts.find(item => item.id === fact.id);
      return <section className={`va-fact va-review-fact ${fact.status}`} key={fact.id} aria-label={`Review ${label(fact.key)}`}><div className="va-fact-label"><h3>{label(fact.key)}</h3><Badge tone={fact.status === 'unresolved' ? 'warning' : ''}>{fact.status === 'rejected' ? 'Removal proposed' : fact.status === 'confirmed' ? 'Selected update' : fact.status === 'unresolved' ? 'Needs confirmation' : 'Suggested'}</Badge></div>
        <div className="va-review-values"><div><span className="va-review-value-label">In use</span><p>{current?.value ?? 'Not in the current brief'}</p></div><div><span className="va-review-value-label">Proposed</span><p>{fact.status === 'rejected' ? 'Remove from the brief' : fact.value}</p></div></div>
        <Sources sources={fact.sources} project={project} onSource={source => { reviewDialog.current?.close(); onSource(source); }} />{!fact.sources.length && <small className="va-muted">{fact.origin === 'manual' ? 'Your direct edit' : 'No source linked · review before use'}</small>}
        <div className="va-fact-controls">{fact.status !== 'rejected' && <label><input type="checkbox" checked={fact.status === 'confirmed'} disabled={factSaving} onChange={event => void updateFact(fact, { status: event.target.checked ? 'confirmed' : 'suggested' })} />Use this update</label>}<button type="button" className="va-link-button" disabled={factSaving} onClick={() => current ? void keepCurrent(fact, current) : void updateFact(fact, { status: 'rejected', permitted_for_use: false })}>{current ? 'Keep current' : 'Dismiss suggestion'}</button>{fact.status !== 'rejected' && <button type="button" className="va-link-button" disabled={factSaving} onClick={() => edit(fact)}>Edit</button>}{current && fact.status !== 'rejected' && <button type="button" className="va-link-button" disabled={factSaving} onClick={() => void updateFact(fact, { status: 'rejected', permitted_for_use: false })}>Remove from brief</button>}</div>
        {isClaimKey(fact.key) && (fact.status === 'rejected' ? <label className="va-claim-permission"><input type="checkbox" checked={claimRemovals.includes(fact.id)} onChange={event => setClaimRemovals(event.target.checked ? [...claimRemovals, fact.id] : claimRemovals.filter(id => id !== fact.id))} />Confirm removing this claim from the brief.</label> : <label className="va-claim-permission"><input type="checkbox" checked={fact.permitted_for_use} disabled={factSaving} onChange={event => void updateFact(fact, { permitted_for_use: event.target.checked })} />Permit this claim’s use. This does not verify its truth.</label>)}
      </section>;
    })}</div>
    {(adding || editing) && <form className="va-fact-editor" onSubmit={event => { event.preventDefault(); void saveCorrection(); }}><h3>{editing ? 'Edit proposed information' : 'Add information'}</h3><label htmlFor={`brief-key-${project.id}`}>Information</label><input id={`brief-key-${project.id}`} autoFocus value={factKey} disabled={factSaving} onChange={event => setFactKey(event.target.value)} placeholder="e.g. audience" required /><label htmlFor={`brief-value-${project.id}`}>Correction</label><textarea id={`brief-value-${project.id}`} value={factValue} disabled={factSaving} onChange={event => setFactValue(event.target.value)} required /><div className="va-actions"><button type="button" onClick={() => { setAdding(false); setEditing(null); }}>Cancel edit</button><button type="submit" disabled={factSaving}>Save suggestion</button></div></form>}
    {!adding && !editing && <button type="button" className="va-link-button" onClick={() => { setAdding(true); setFactKey(''); setFactValue(''); }}>Add information</button>}
    {currentFacts.length > 0 && <details className="va-review-history"><summary>Edit current information</summary>{currentFacts.map(fact => <div key={fact.id}><p><strong>{label(fact.key)}:</strong> {fact.value}</p><button type="button" className="va-link-button" disabled={factSaving} onClick={() => edit(facts.find(item => item.id === fact.id) ?? fact)}>Propose a change</button><button type="button" className="va-link-button" disabled={factSaving} onClick={() => void updateFact(facts.find(item => item.id === fact.id) ?? fact, { status: 'rejected', permitted_for_use: false })}>Remove from brief</button></div>)}</details>}
    {(project.unresolved.length > 0 || facts.some(fact => fact.status === 'rejected' && !currentFacts.some(item => item.id === fact.id))) && <details className="va-review-history"><summary>Unresolved and dismissed suggestions</summary>{project.unresolved.length > 0 && <ul>{project.unresolved.map((item, index) => <li key={index}>{item}</li>)}</ul>}{facts.filter(fact => fact.status === 'rejected' && !currentFacts.some(item => item.id === fact.id)).map(fact => <div key={fact.id}><p>{label(fact.key)}: {fact.value}</p><button type="button" className="va-link-button" disabled={factSaving} onClick={() => void updateFact(fact, { status: 'suggested' })}>Restore suggestion</button></div>)}</details>}
    <div className="va-review-footer"><p className="va-muted">{missingClaimPermission ? 'Explicit permission is required for each selected claim.' : unconfirmedRemoval ? 'Confirm the claim removal before applying.' : 'Unselected proposals stay separate. Earlier brief versions remain available.'}</p><div className="va-actions"><button type="button" onClick={() => reviewDialog.current?.close()}>Close</button><button type="button" className="va-primary" disabled={!canApply || adding || Boolean(editing)} onClick={() => void apply()}>Apply updates</button></div></div>
  </dialog>
  </div>;
}
