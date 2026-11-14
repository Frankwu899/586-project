import { useEffect, useRef, useState } from 'react';
import type { Fact, Project } from './contracts';
import { FailureNotice, Badge, DraftConflict, Icon, Sources, type SourceAction } from './Common';
import { useDraft, type Mutate } from './client';

export default function Overview({ project, mutate, onSource }: { project: Project; mutate: Mutate; onSource: SourceAction }) {
  const [composer, setComposer, flushComposer, composerConflict, reloadComposer] = useDraft(project, 'conversation', { text: project.conversation_draft, resource_ids: [] as string[] }, mutate);
  const [sending, setSending] = useState(false);
  const [uploading, setUploading] = useState(false);
  const composerRef = useRef(composer);
  composerRef.current = composer;
  const [editing, setEditing] = useState<Fact | null>(null);
  const [adding, setAdding] = useState(false);
  const [factKey, setFactKey] = useState('');
  const [factValue, setFactValue] = useState('');
  const attachment = useRef<HTMLInputElement>(null);
  const currentBrief = project.briefs.at(-1);
  const recoveryKey = `video-anatomy:1.8:${project.id}:brief-recovery`;
  const [recovered] = useState(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(recoveryKey) ?? 'null') as { facts: Fact[]; base_version: number } | null;
      if (stored && Array.isArray(stored.facts) && typeof stored.base_version === 'number' && JSON.stringify(stored.facts) !== JSON.stringify(project.brief_draft)) return stored;
    } catch { /* The saved project remains authoritative. */ }
    return null;
  });
  const [facts, setFacts] = useState(recovered?.facts ?? project.brief_draft);
  const [factSaving, setFactSaving] = useState(false);
  const [factFailed, setFactFailed] = useState(Boolean(recovered));
  const factVersion = useRef(recovered?.base_version ?? project.brief_draft_version);
  useEffect(() => {
    if (!factSaving && !factFailed) { setFacts(project.brief_draft); factVersion.current = project.brief_draft_version; }
  }, [project.brief_draft, project.brief_draft_version, factSaving, factFailed]);
  const persistFacts = async (next: Fact[]) => {
    setFacts(next); setFactSaving(true);
    try { localStorage.setItem(recoveryKey, JSON.stringify({ facts: next, base_version: factVersion.current })); } catch { /* The project save still runs. */ }
    const saved = await mutate('/brief/draft', { expected_draft_version: factVersion.current, facts: next });
    if (saved) { setFacts(saved.brief_draft); factVersion.current = saved.brief_draft_version; setFactFailed(false); localStorage.removeItem(recoveryKey); }
    else setFactFailed(true);
    setFactSaving(false); return saved;
  };
  const updateFact = (fact: Fact, changes: Partial<Fact>) => persistFacts(facts.map(item => item.id === fact.id ? { ...item, ...changes } : item));
  const send = async () => {
    if (!composer.text.trim() || sending || uploading) return;
    setSending(true);
    if (!await flushComposer()) { setSending(false); return; }
    const text = composer.text;
    const saved = await mutate('/messages', { text, resource_ids: composer.resource_ids });
    if (saved) { setComposer({ text: '', resource_ids: [] }); void mutate('', { conversation_draft: '' }, 'PATCH'); }
    setSending(false);
  };
  const upload = async (files: FileList | null) => {
    if (!files) return;
    setUploading(true);
    const ids: string[] = [];
    for (const file of Array.from(files)) {
      const data = new FormData(); data.append('file', file); data.append('role', 'document');
      const saved = await mutate('/resources', data);
      if (saved) { const added = saved.resources.at(-1); if (added) ids.push(added.id); }
    }
    setComposer({ ...composerRef.current, resource_ids: [...new Set([...composerRef.current.resource_ids, ...ids])] });
    setUploading(false);
  };
  const saveCorrection = async () => {
    if (!factKey.trim() || !factValue.trim()) return;
    const changed = editing ? { ...editing, key: factKey.trim(), value: factValue.trim(), status: 'suggested' as const, permitted_for_use: false } : { id: `fact_${crypto.randomUUID().replaceAll('-', '')}`, key: factKey.trim(), value: factValue.trim(), status: 'suggested' as const, origin: 'manual' as const, sources: [], permitted_for_use: false };
    const result = await persistFacts(editing ? facts.map(item => item.id === editing.id ? changed : item) : [...facts, changed]);
    if (result) { setEditing(null); setAdding(false); }
  };
  return <div className="va-overview"><section className="va-conversation va-glass"><div className="va-conversation-heading"><span className="va-eyebrow">YOUR CREATIVE ASSIGNMENT</span><h1>{project.messages.length ? 'Let’s shape the assignment.' : 'What do you want to create today?'}</h1><p>Attach a brief, paste notes, or describe the assignment.</p></div>
    <div className="va-messages" aria-live="polite">{!project.messages.length && <div className="va-conversation-welcome"><Icon name="spark" size={35} /><p>Start with what you know. We’ll organize the context and work through the important gaps together.</p><div className="va-prompt-hints"><span>Plan a content series</span><span>Develop a video idea</span><span>Understand references</span></div></div>}{project.messages.map(message => <article key={message.id} className={`va-message ${message.role}`}><div className="va-message-avatar">{message.role === 'assistant' ? <Icon name="spark" /> : 'You'}</div><div className="va-message-body">{message.status === 'failed' ? <FailureNotice message={message.text} detail={`Message ${message.id}`} /> : <p>{message.text}</p>}{message.resource_ids.length > 0 && <div className="va-sources">{message.resource_ids.map(id => <button key={id} onClick={() => onSource({ resource_id: id, message_id: null, locator: '', excerpt: '', url: null, evidence_revision: null, extraction_revision: null, event_id: null, start_seconds: null, end_seconds: null })}><Icon name="file" size={14} />{project.resources.find(resource => resource.id === id)?.name ?? 'Attachment'}</button>)}</div>}{message.status === 'failed' && <Badge tone="warning">Assistance incomplete · message saved</Badge>}</div></article>)}{sending && <p className="va-assistant-working" role="status"><span className="va-spinner" />Organizing your assignment…</p>}</div>
    <DraftConflict conflict={composerConflict} reload={reloadComposer} /><form className="va-composer" onSubmit={event => { event.preventDefault(); void send(); }}><div className="va-attachment-row">{composer.resource_ids.map(id => { const resource = project.resources.find(item => item.id === id); return <span key={id}><Icon name="file" size={15} />{resource?.name ?? 'Attachment'}<Badge>{resource?.status ?? 'Saved'}</Badge><button type="button" aria-label={`Detach ${resource?.name ?? 'file'}`} onClick={() => setComposer({ ...composer, resource_ids: composer.resource_ids.filter(value => value !== id) })}>×</button></span>; })}</div><label className="va-sr-only" htmlFor={`message-${project.id}`}>Describe your assignment</label><textarea id={`message-${project.id}`} placeholder="Add context or ask a question…" value={composer.text} disabled={sending} onChange={event => setComposer({ ...composer, text: event.target.value })} onBlur={() => { void mutate('', { conversation_draft: composer.text }, 'PATCH'); }} onKeyDown={event => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void send(); } }} /><div className="va-composer-footer"><span>Draft saved locally · ⌘ / Ctrl + Enter to send</span><input ref={attachment} type="file" tabIndex={-1} className="va-sr-only" multiple onChange={event => { void upload(event.target.files); event.target.value = ''; }} /><button type="button" className="va-icon-button" aria-label="Attach documents" disabled={sending || uploading} onClick={() => attachment.current?.click()}><Icon name="upload" /></button><button type="submit" className="va-primary va-send" disabled={!composer.text.trim() || sending || uploading} aria-label="Send message"><Icon name="send" /></button></div></form>
  </section><aside className="va-overview-inspector"><section className="va-glass va-brief"><div className="va-section-heading"><h2>Project brief</h2><Badge>{currentBrief ? `Applied v${currentBrief.revision}` : 'Working draft'}</Badge></div><p className="va-muted">Review what’s understood. Correct anything through the conversation.</p>{factSaving && <p role="status" className="va-muted">Saving proposed information…</p>}{factFailed && <div className="va-notice" role="alert">Your proposed changes are retained on this computer but are not saved to the project.<button onClick={() => void persistFacts(facts)}>Retry draft save</button><button onClick={() => { if (window.confirm('Replace your retained changes with the current saved brief draft?')) { setFacts(project.brief_draft); factVersion.current = project.brief_draft_version; setFactFailed(false); localStorage.removeItem(recoveryKey); } }}>Reload saved draft</button></div>}{!facts.length && <p className="va-brief-empty">Your audience, objective, format, and constraints will appear here as the assignment takes shape.</p>}{facts.filter(fact => fact.status !== 'rejected').map(fact => <div className={`va-fact ${fact.status}`} key={fact.id}><div className="va-fact-label"><span>{fact.key.replaceAll('_', ' ')}</span><Badge tone={fact.status === 'unresolved' ? 'warning' : fact.status === 'confirmed' ? 'success' : ''}>{fact.status}</Badge></div><p>{fact.value}</p><Sources sources={fact.sources} project={project} onSource={onSource} /><div className="va-fact-controls"><label><input type="checkbox" checked={fact.status === 'confirmed'} disabled={factSaving} onChange={event => void updateFact(fact, { status: event.target.checked ? 'confirmed' : 'suggested' })} />Confirm for brief</label><button className="va-link-button" onClick={() => { setEditing(fact); setAdding(false); setFactKey(fact.key); setFactValue(fact.value); }}>Correct</button><button className="va-link-button" disabled={factSaving} onClick={() => void updateFact(fact, { status: 'rejected', permitted_for_use: false })}>Exclude</button></div>{/claim|selling_point|approved_message/i.test(fact.key) && <label className="va-claim-permission"><input type="checkbox" checked={fact.permitted_for_use} disabled={factSaving} onChange={event => void updateFact(fact, { permitted_for_use: event.target.checked })} />Permit this claim’s use. This does not verify its truth.</label>}</div>)}
    {facts.some(fact => fact.status === 'rejected') && <details className="va-excluded-facts"><summary>Excluded information</summary>{facts.filter(fact => fact.status === 'rejected').map(fact => <div key={fact.id}><p>{fact.key}: {fact.value}</p><button className="va-link-button" disabled={factSaving} onClick={() => void updateFact(fact, { status: 'suggested' })}>Restore suggestion</button></div>)}</details>}
    {(adding || editing) && <form className="va-fact-editor" onSubmit={event => { event.preventDefault(); void saveCorrection(); }}><label>Information<input value={factKey} disabled={factSaving} onChange={event => setFactKey(event.target.value)} placeholder="e.g. audience" required /></label><label>Correction<textarea value={factValue} disabled={factSaving} onChange={event => setFactValue(event.target.value)} required /></label><div className="va-actions"><button type="button" onClick={() => { setAdding(false); setEditing(null); }}>Cancel</button><button type="submit" disabled={factSaving}>Save suggestion</button></div></form>}
    {!adding && !editing && <button className="va-link-button" onClick={() => { setAdding(true); setFactKey(''); setFactValue(''); }}>Add a correction directly</button>}{project.unresolved.length > 0 && <div className="va-notice"><strong>Still to resolve</strong><ul>{project.unresolved.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}<button className="va-primary va-full-width" disabled={factSaving || factFailed || !facts.some(fact => fact.status === 'confirmed')} onClick={() => void mutate('/brief/apply', { expected_draft_version: factVersion.current, facts })}>Apply confirmed brief</button><small className="va-muted">Only this action adopts changes for new creative work. Earlier versions remain available.</small></section>
    <section className="va-glass va-resource-summary"><h2>Project resources</h2><p><Icon name="resources" />{project.resources.length} files saved locally</p><button onClick={() => attachment.current?.click()}><Icon name="upload" />Attach files</button></section>
  </aside></div>;
}
