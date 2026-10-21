import { useI18n } from './i18n';
import { useState } from 'react';
import type { M2Draft, M2AssistanceResponse, M2Candidate } from './generated/contracts';
import { request } from './api';
import { Field } from './ui';
import type { M2DraftSession } from './m2DraftSession';

type Props = { taskId: string; session: M2DraftSession; locked: boolean; onBusy: (busy: boolean) => void };
const names: Record<string, string> = { brand_company: 'Brand/company', product: 'Product', target_audience: 'Target audience', platform: 'Publishing platform', communication_goal: 'Communication goal', target_duration_seconds: 'Target duration (seconds)', claim: 'Selling point', approved_messages: 'Approved messages', prohibited_claims: 'Prohibited claims' };
const display = (value: unknown): string => value === null || value === undefined || value === '' ? 'Not provided' : Array.isArray(value) ? value.join('\n') || 'Not provided' : typeof value === 'object' && 'statement' in value ? String(value.statement) : String(value);

export default function M2Proposals({ taskId, session, locked, onBusy }: Props) {
  const { t } = useI18n();
  const [batch, setBatch] = useState<M2AssistanceResponse | null>(null);
  const [generation, setGeneration] = useState<number | null>(null);
  const [rows, setRows] = useState<M2Candidate[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const extractionPrefix = 'Couldn’t extract details. You can continue editing.';
  const displayError = error.startsWith(extractionPrefix) ? `${t(extractionPrefix)} ${t(error.slice(extractionPrefix.length).trim())}` : t(error);
  const stale = Boolean(batch && (generation !== session.generation || batch.source_draft_version !== session.current.draft_version));
  const assist = async (field: 'target_audience' | 'communication_goal' | null = null) => {
    setLoading(true); setError(''); setNotice(''); setBatch(null);
    try {
      const saved = await session.flush();
      const sourceGeneration = session.generation;
      const result = await request<M2AssistanceResponse>(`/tasks/${taskId}/m2/assist`, { draft_version: saved.draft_version, request_id: `m2_${crypto.randomUUID()}`, mode: field ? 'suggest_task_field' : 'extract', requested_field: field });
      setBatch(result); setGeneration(sourceGeneration); setRows(result.candidates); setSelected(new Set());
    } catch (failure) { setError(`Couldn’t extract details. You can continue editing. ${failure instanceof Error ? failure.message : 'Try again when assistance is available.'}`); }
    finally { setLoading(false); }
  };
  const adopt = async () => {
    if (!batch || stale || !selected.size) return;
    onBusy(true); setError('');
    try {
      const saved = await request<M2Draft>(`/tasks/${taskId}/m2/adopt`, { source_draft_version: batch.source_draft_version, request_id: batch.request_id, candidates: rows.filter((candidate) => selected.has(candidate.candidate_id)) });
      session.replace(saved); setBatch(null); setRows([]); setSelected(new Set());
      setNotice('Selected details added to your draft. Confirm selling points and review inputs before applying.');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not use these details. Your existing inputs are retained.'); }
    finally { onBusy(false); }
  };
  const update = (candidateId: string, value: M2Candidate['value']) => setRows((previous) => previous.map((candidate) => candidate.candidate_id === candidateId ? { ...candidate, value } : candidate));
  return <div className="m2-assistance">
    <div className="actions"><button type="button" className="secondary" disabled={loading || locked || !session.current.source_notes.trim()} onClick={() => void assist()}>{loading ? t("Extracting details…") : t("Extract details")}</button><button type="button" className="text-button" disabled={loading || locked} onClick={() => void assist('target_audience')}>{t("Suggest an audience")}</button><button type="button" className="text-button" disabled={loading || locked} onClick={() => void assist('communication_goal')}>{t("Suggest a communication goal")}</button></div>
    {loading && <p role="status">{t("Extracting details from your notes… You can keep editing.")}</p>}
    {error && <p role="alert" className="error">{displayError} <button type="button" className="secondary" onClick={() => void assist()} disabled={loading || locked}>{t("Try again")}</button></p>}
    {notice && <p role="status" className="success">{t(notice)}</p>}
    {batch && <section className="m2-proposals" aria-label={t("Review proposed details")}><h3>{t("Review proposed details")}</h3>{batch.provider_mode === 'fake' && <p className="notice">{t("Deterministic test assistance · not real AI extraction.")}</p>}<p>{t("Choose the details to add. Edit the proposed wording before using it; existing values are shown for comparison.")}</p>{stale && <p role="alert" className="error">{t("Your inputs changed. Run extraction again. Newer text has been kept.")}</p>}{batch.unresolved_notes.map((note, index) => <p className="muted" key={index}>{note}</p>)}
      {!rows.length && <p>{t("No supported details were found. Continue with manual editing.")}</p>}
      {rows.map((candidate, index) => {
        const label = t(names[candidate.target] ?? candidate.target.replaceAll('_', ' '));
        const claim = typeof candidate.value === 'object' && candidate.value !== null && !Array.isArray(candidate.value) ? candidate.value : null;
        const oldValue = candidate.target === 'claim' ? t('New selling point — needs your confirmation') : session.current.fields[candidate.target as keyof M2Draft['fields']];
        return <article className="m2-proposal" key={candidate.candidate_id}>
          <div className="m2-section-title"><label className="m2-confirm"><input type="checkbox" checked={selected.has(candidate.candidate_id)} disabled={stale || locked} onChange={(event) => setSelected((previous) => { const next = new Set(previous); if (event.target.checked) next.add(candidate.candidate_id); else next.delete(candidate.candidate_id); return next; })} />{t("Select")} {label}<span className="sr-only">  {t("proposal")} {index + 1}</span></label><button type="button" className="text-button" onClick={() => { setRows((previous) => previous.filter((row) => row.candidate_id !== candidate.candidate_id)); setSelected((previous) => { const next = new Set(previous); next.delete(candidate.candidate_id); return next; }); }} disabled={locked}>{t("Dismiss")}<span className="sr-only"> {label}  {t("proposal")} {index + 1}</span></button></div>
          <small>{candidate.origin === 'extracted' ? t("From your notes") : t("Suggested — confirm before use")}{claim ? t(" · Needs your confirmation") : ''}</small>
          {candidate.source_excerpt && <blockquote><span className="sr-only">{t("Exact source excerpt:")} </span>{candidate.source_excerpt}</blockquote>}
          <p className="m2-current"><strong>{t("Current:")}</strong> {display(oldValue) === "Not provided" ? t("Not provided") : display(oldValue)}</p>
          <Field label={t("Proposed {label} {index}", { label, index: index + 1 })}><textarea disabled={stale || locked} value={display(candidate.value) === 'Not provided' ? '' : display(candidate.value)} onChange={(event) => update(candidate.candidate_id, claim ? { ...claim, statement: event.target.value } : typeof candidate.value === 'number' ? Number(event.target.value) : Array.isArray(candidate.value) ? event.target.value.split('\n').filter((line) => line.trim()) : event.target.value)} /></Field>
          {claim && <><Field label={t("Proposed qualification {index}", { index: index + 1 })}><textarea disabled={stale || locked} value={claim.qualification ?? ''} onChange={(event) => update(candidate.candidate_id, { ...claim, qualification: event.target.value || null })} /></Field>{claim.supporting_notes && <p>{t("Support supplied:")} {claim.supporting_notes}</p>}{claim.source_urls.length > 0 && <p>{t("Source links:")} {claim.source_urls.join(', ')}</p>}</>}
        </article>;
      })}
      <div className="actions"><button type="button" disabled={locked || stale || !selected.size} onClick={() => void adopt()}>{t("Use selected details")}</button>{stale && <button type="button" className="secondary" disabled={loading || locked} onClick={() => void assist()}>{t("Run extraction again")}</button>}</div>
    </section>}
  </div>;
}
