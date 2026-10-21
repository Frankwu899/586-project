import { useEffect, useState } from 'react';
import { request } from './api';
import { registerTranslations, useI18n } from './i18n';

registerTranslations({
  'API usage': 'API 用量',
  'No client-side spending cap': '客户端不设费用上限',
  'Recorded requests': '已记录请求',
  'Requests with unconfirmed cost': '费用未确认的请求',
  'Recorded estimates are not your OpenAI balance or invoice. OpenAI account limits still apply.': '记录中的估算不是 OpenAI 余额或账单，仍适用 OpenAI 账户限制。',
  'Refresh usage': '刷新用量',
  'Usage records are incomplete. This does not block generation.': '用量记录不完整，不影响生成。',
  'Local test budget': '本地测试预算',
  'Remaining': '可用额度',
  'Estimated usage': '已估算用量',
  'Unresolved reservations': '待结算预留',
  'This app limit is separate from your OpenAI account balance. Estimates are not an invoice.': '此应用额度独立于 OpenAI 账户余额，估算不等于账单。',
  'Release rejected requests': '释放被拒请求的预留',
  'Only confirmed authentication or permission refusals can be released. Timeouts and unknown charges stay reserved.': '仅释放明确认证或权限拒绝的预留；超时和未知费用继续保留。',
  'Refresh budget': '刷新预算',
  'Budget updated. Completed work and the spending limit are unchanged.': '预算已更新，已完成内容和费用上限均保留。',
  'Could not load budget.': '无法读取预算。',
  'API spending is paused for an accounting check. Releasing rejected requests does not remove this pause.': '费用核对期间已暂停 API 调用。释放被拒请求的预留不会解除此暂停。',
});

interface Budget {
  enforced?: boolean;
  mode?: 'usage_only';
  attempts?: number;
  unknown_attempts?: number;
  usage_records_available?: boolean;
  unreadable_records?: number;
  maximum_usd: string | null;
  remaining_usd: string | null;
  known_estimated_cost_usd: string;
  unresolved_reserved_usd: string;
  recoverable_rejected_attempts: number;
  blocked: boolean;
}
export default function BudgetStatus() {
  const { t } = useI18n();
  const [budget, setBudget] = useState<Budget | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useEffect(() => {
    let live = true;
    void request<Budget>('/local/budget').then((value) => { if (live) setBudget(value); }).catch(() => {
      if (live) setError('Could not load budget.');
    });
    return () => { live = false; };
  }, []);
  async function refresh(reconcile: boolean) {
    if (pending) return;
    setPending(true); setError(''); setNotice('');
    try {
      setBudget(await request<Budget>(reconcile ? '/local/budget/reconcile' : '/local/budget', reconcile ? {} : undefined));
      if (reconcile) setNotice('Budget updated. Completed work and the spending limit are unchanged.');
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Could not load budget.'); }
    finally { setPending(false); }
  }
  const dollars = (value: string) => `$${Number(value).toFixed(3)}`;
  if (budget?.enforced === false) return <section className="connection-budget" aria-label={t('API usage')}>
    <h3>{t('API usage')}</h3>
    <p>{t('No client-side spending cap')}</p>
    <dl className="budget-totals">
      <div><dt>{t('Estimated usage')}</dt><dd>{dollars(budget.known_estimated_cost_usd)}</dd></div>
      <div><dt>{t('Recorded requests')}</dt><dd>{budget.attempts ?? 0}</dd></div>
      <div><dt>{t('Requests with unconfirmed cost')}</dt><dd>{budget.unknown_attempts ?? 0}</dd></div>
    </dl>
    <p className="muted">{t('Recorded estimates are not your OpenAI balance or invoice. OpenAI account limits still apply.')}</p>
    {(budget.usage_records_available === false || !!budget.unreadable_records) && <p role="status">{t('Usage records are incomplete. This does not block generation.')}</p>}
    <button type="button" className="text-button" disabled={pending} onClick={() => void refresh(false)}>{t('Refresh usage')}</button>
    {error && <p className="error" role="alert">{t(error)}</p>}
  </section>;
  return <section className="connection-budget" aria-label={t('Local test budget')}>
    <h3>{t('Local test budget')}{budget ? ` · $${Number(budget.maximum_usd).toFixed(2)}` : ''}</h3>
    {budget?.blocked && <p className="error" role="alert">{t('API spending is paused for an accounting check. Releasing rejected requests does not remove this pause.')}</p>}
    {budget && <dl className="budget-totals">
      <div><dt>{t('Remaining')}</dt><dd>{dollars(budget.remaining_usd ?? '0')}</dd></div>
      <div><dt>{t('Estimated usage')}</dt><dd>{dollars(budget.known_estimated_cost_usd)}</dd></div>
      <div><dt>{t('Unresolved reservations')}</dt><dd>{dollars(budget.unresolved_reserved_usd)}</dd></div>
    </dl>}
    <p className="muted">{t('This app limit is separate from your OpenAI account balance. Estimates are not an invoice.')}</p>
    {!!budget?.recoverable_rejected_attempts && <>
      <p>{t('Only confirmed authentication or permission refusals can be released. Timeouts and unknown charges stay reserved.')}</p>
      <button type="button" className="secondary" disabled={pending} onClick={() => void refresh(true)}>{t('Release rejected requests')} ({budget.recoverable_rejected_attempts})</button>
    </>}
    <button type="button" className="text-button" disabled={pending} onClick={() => void refresh(false)}>{t('Refresh budget')}</button>
    {notice && <p role="status">{t(notice)}</p>}
    {error && <p className="error" role="alert">{t(error)}</p>}
  </section>;
}
