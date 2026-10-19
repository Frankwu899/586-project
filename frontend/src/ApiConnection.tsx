import { useI18n } from './i18n';
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { request } from './api';
import { Field } from './ui';
import BudgetStatus from './BudgetStatus';
import './connection.css';

interface ConnectionCheck {
  status: 'verified' | 'unverified' | 'rejected';
  code: string;
  message: string;
  missing_models: string[];
  endpoint_permissions_verified: false;
}
interface ConnectionStatus {
  available: boolean;
  configured: boolean;
  key_source: 'keychain' | 'session' | 'environment' | 'none';
  can_remember: boolean;
  remembered: boolean;
  keychain_error?: string;
  last_check: ConnectionCheck | null;
}
const ConnectionContext = createContext<{ status: ConnectionStatus | null; open: () => void }>({ status: null, open: () => {} });

export function ApiConnectionButton() {
  const { t } = useI18n();
  const { status, open } = useContext(ConnectionContext);
  if (!status?.available) return null;
  return <button type="button" className="secondary connection-toggle" onClick={open}><span className={`connection-dot ${status.configured ? 'configured' : ''}`} aria-hidden="true" />{t("API connection")}<span className="connection-indicator">{status.configured ? t("Key added") : t("Set up")}</span></button>;
}

export function ConnectionHelp({ message }: { message?: string }) {
  const { t } = useI18n();
  const { status, open } = useContext(ConnectionContext);
  if (!status?.available || !message || !/authenticat|API (?:key|credential|settings|connection)|(?:account|key) permissions|provider.*permission|not configured|not enabled|experiment budget|budget cannot|budget exhausted/i.test(message)) return null;
  return <button type="button" className="text-button connection-help" onClick={open}>{t("Check API connection")}</button>;
}

export default function ApiConnection({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [open, setOpen] = useState(false);
  const [key, setKey] = useState('');
  const [remember, setRemember] = useState(false);
  const [pending, setPending] = useState('');
  const [error, setError] = useState('');
  const [check, setCheck] = useState<ConnectionCheck | null>(null);
  const [notice, setNotice] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    let cancelled = false;
    // This route exists only in the local launcher, not the hosted/dev API.
    void request<ConnectionStatus>('/local/connection').then((value) => {
      if (cancelled || !value.available) return;
      setStatus(value); setRemember(value.can_remember); setCheck(value.last_check);
      if (!value.configured) setOpen(true);
    }).catch(() => { /* Older and development servers have no credential UI. */ });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (open) { dialog.current?.showModal(); input.current?.focus(); }
    else dialog.current?.close();
  }, [open]);
  const close = () => { setOpen(false); setKey(''); setError(''); setNotice(''); setCheck(status?.last_check ?? null); };
  const show = () => { setError(''); setNotice(''); setCheck(status?.last_check ?? null); setOpen(true); };
  const perform = async (action: 'check' | 'save' | 'forget') => {
    if (!status || pending || (action === 'save' && !key.trim())) return;
    setPending(action); setError(''); setNotice('');
    try {
      if (action === 'check') {
        const result = await request<ConnectionCheck>('/local/connection/check', key.trim() ? { api_key: key.trim() } : {});
        setCheck(result);
        if (!key.trim()) setStatus({ ...status, last_check: result });
      } else {
        const saved = action === 'save'
          ? await request<ConnectionStatus>('/local/connection', { api_key: key.trim(), remember: status.can_remember && remember })
          : await request<ConnectionStatus>('/local/connection/forget', {});
        setStatus(saved); setCheck(saved.last_check); setKey('');
        setNotice(action === 'forget' ? 'Connection cleared. Your projects and videos are unchanged.' : saved.remembered ? 'Saved in macOS Keychain. You can reopen the app without entering the key again.' : 'Key added for this session. You can continue in your project.');
      }
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not update the API connection.'); }
    finally { setPending(''); }
  };
  return <ConnectionContext.Provider value={{ status, open: show }}>{children}
    <dialog ref={dialog} className="connection-dialog" aria-labelledby="connection-title" onCancel={(event) => { event.preventDefault(); close(); }}>
      <header><div><h2 id="connection-title">{t("API connection")}</h2><p>{t("Connect OpenAI to analyze videos and develop ideas.")}</p></div><button type="button" className="text-button" onClick={close} aria-label={t("Close API connection")}>{t("Close")}</button></header>
      {status && <form onSubmit={(event) => { event.preventDefault(); void perform('save'); }}>
        <p className="connection-current">{status.configured ? status.key_source === 'keychain' ? t("Current key: saved in macOS Keychain.") : status.key_source === 'environment' ? t("Current key: provided by your launcher environment.") : t("Current key: available for this session.") : t("No API key added yet.")}</p>
        <Field label={status.configured ? t("Replace API key") : t("OpenAI API key")} hint={t("Paste the complete secret key. Storage is local to this computer, never in browser storage.")}><input ref={input} type="password" value={key} onChange={(event) => { setKey(event.target.value); setCheck(null); setError(''); setNotice(''); }} autoComplete="new-password" autoCapitalize="none" spellCheck={false} disabled={Boolean(pending)} placeholder={status.configured ? t("Leave blank to check the current key") : t("sk-…")} /></Field>
        {status.can_remember ? <label className="connection-remember"><input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} disabled={Boolean(pending)} />{t("Remember on this Mac (Keychain)")}</label> : <p className="muted">{t("This launcher keeps keys for the current session only.")}</p>}
        {status.keychain_error && <p className="notice">{t(status.keychain_error)}</p>}
        {pending && <p className="connection-progress" role="status"><span className="spinner" aria-hidden="true" />{pending === 'forget' ? t("Removing key…") : t("Checking connection…")}</p>}
        {error && <p className="error" role="alert">{t(error)}</p>}
        {!error && check && <div className={check.status === 'rejected' ? 'error' : 'notice'} role={check.status === 'rejected' ? 'alert' : 'status'}><p>{t(check.message)}</p>{check.missing_models.length > 0 && <p>{t("Models not listed:")} {check.missing_models.join(', ')}.</p>}</div>}
        {notice && <p role="status" className="connection-success">{t(notice)}</p>}
        <p className="connection-check-note">{t("Connection checks do not generate content or use paid model calls. Generation access and account credit are confirmed when you run an analysis.")}</p>
        <div className="connection-actions"><button type="button" className="secondary" disabled={Boolean(pending) || (!key.trim() && !status.configured)} onClick={() => void perform('check')}>{t("Check connection")}</button><button type="submit" disabled={Boolean(pending) || !key.trim()}>{t("Save key")}</button></div>
        {status.configured && <button type="button" className="text-button connection-forget" disabled={Boolean(pending)} onClick={() => void perform('forget')}>{t("Remove API key")}</button>}
      </form>}
      {open && <BudgetStatus />}
    </dialog>
  </ConnectionContext.Provider>;
}
