import { useState, type ReactNode } from 'react';
import { failureMessage, safeDiagnostic, supportText } from './status';
import type { Project, SourceRef } from './contracts';

const paths: Record<string, string> = {
  projects: 'M3 7h7l2 2h9v11H3z M3 7V4h7l2 3', overview: 'm3 11 9-8 9 8 M5 10v11h14V10 M9 21v-7h6v7',
  resources: 'M3 7h7l2 2h9v11H3z M3 7V4h7l2 3', discover: 'M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0 M15 9l-2 4-4 2 2-4z',
  analysis: 'M5 20v-7 M12 20V4 M19 20V9', content: 'M4 5h16v16H4z M4 10h16 M8 3v4 M16 3v4', production: 'M3 7h18v14H3z M3 7l3-4h15v4 M8 3l-3 4 M15 3l-3 4',
  plus: 'M12 5v14 M5 12h14', search: 'M17 10a7 7 0 1 1-14 0 7 7 0 0 1 14 0 M15 15l6 6', back: 'm10 5-7 7 7 7 M3 12h18',
  trash: 'M3 6h18 M8 6V3h8v3 M6 6l1 15h10l1-15 M10 10v7 M14 10v7', check: 'm5 12 4 4L19 6', send: 'm3 3 19 9-19 9 4-9z M7 12h15',
  upload: 'M12 16V3 m-5 5 5-5 5 5 M4 16v5h16v-5', file: 'M5 3h9l5 5v13H5z M14 3v6h5', play: 'm8 4 12 8-12 8z',
  settings: 'M4 7h16 M4 17h16 M8 4v6 M16 14v6', close: 'm6 6 12 12 M18 6 6 18', spark: 'm12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3z',
};
export function Icon({ name, size = 20 }: { name: string; size?: number }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] ?? paths.file} /></svg>; }
export function Brand() { return <div className="va-brand"><span className="va-mark"><Icon name="play" size={25} /></span><strong>Video Anatomy</strong><span className="va-version">1.8.3</span></div>; }
export function Badge({ children, tone = '' }: { children: ReactNode; tone?: string }) { return <span className={`va-badge ${tone}`}>{children}</span>; }
export function DraftConflict({ conflict, reload }: { conflict: boolean; reload: () => void }) { return conflict ? <div className="va-notice" role="alert">A newer draft was saved elsewhere. Your local text is retained for comparison.<button type="button" onClick={() => { if (window.confirm('Replace this retained local draft with the current saved draft? Copy any local text you want to keep first.')) reload(); }}>Load saved draft</button></div> : null; }
export function Empty({ title, children }: { title: string; children?: ReactNode }) { return <div className="va-empty"><Icon name="spark" size={32} /><h3>{title}</h3>{children}</div>; }
export function time(seconds: number) { return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`; }
export function date(value: string) { return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); }
export type SourceAction = (source: SourceRef) => void;
export function Sources({ sources, project, onSource }: { sources: SourceRef[]; project: Project; onSource: SourceAction }) {
  return sources.length ? <div className="va-sources">{sources.map((source, index) => {
    const resource = project.resources.find(item => item.id === source.resource_id);
    const label = [resource?.name ?? (source.message_id ? 'Conversation' : 'Source'), source.locator, source.start_seconds != null ? time(source.start_seconds) : ''].filter(Boolean).join(' · ');
    if (source.url && !resource) return <a key={index} href={/^https?:\/\//.test(source.url) ? source.url : undefined} target="_blank" rel="noreferrer">{label}<span aria-hidden="true"> ↗</span></a>;
    return <button key={index} type="button" onClick={() => onSource(source)} title={source.excerpt}><Icon name={source.start_seconds != null ? 'play' : 'file'} size={14} />{label}</button>;
  })}</div> : null;
}

export function SupportDetails({ diagnostics, detail, label = 'Support details' }: { diagnostics?: Record<string, unknown> | Record<string, unknown>[]; detail?: string; label?: string }) {
  const [copyState, setCopyState] = useState('');
  const technical = supportText(diagnostics);
  const content = [technical, detail ? safeDiagnostic(detail) : ''].filter(Boolean).join('\n');
  if (!content) return null;
  const exportDetails = () => {
    const url = URL.createObjectURL(new Blob([content + '\n'], { type: 'text/plain;charset=utf-8' }));
    const link = document.createElement('a'); link.href = url; link.download = 'video-anatomy-support.txt'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <details className="va-support"><summary>{label}</summary><p className="va-muted">Operational details only. Prompts, source contents and credentials are excluded.</p><pre>{content}</pre><div className="va-actions"><button type="button" onClick={() => { if (!navigator.clipboard) { setCopyState('Copy unavailable. Use Export support details.'); return; } void navigator.clipboard.writeText(content).then(() => setCopyState('Copied')).catch(() => setCopyState('Copy unavailable. Use Export support details.')); }}>Copy support details</button><button type="button" onClick={exportDetails}>Export support details</button></div>{copyState && <p role="status">{copyState}</p>}</details>;
}

export function FailureNotice({ message, detail, code, diagnostics }: { message: string; detail?: string; code?: string | null; diagnostics?: Record<string, unknown> | Record<string, unknown>[] }) {
  return <div className="va-error" role="alert"><p>{failureMessage(message, code)}</p><SupportDetails diagnostics={diagnostics} detail={detail} /></div>;
}
