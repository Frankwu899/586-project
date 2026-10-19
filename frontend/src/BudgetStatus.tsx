import { useEffect, useState } from 'react';
import { request } from './api';
import { registerTranslations, useI18n } from './i18n';

registerTranslations({
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
  maximum_usd: string;
  remaining_usd: string;
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
  return <section className="connection-budget" aria-label={t('Local test budget')}>
    <h3>{t('Local test budget')}{budget ? ` · $${Number(budget.maximum_usd).toFixed(2)}` : ''}</h3>
    {budget?.blocked && <p className="error" role="alert">{t('API spending is paused for an accounting check. Releasing rejected requests does not remove this pause.')}</p>}
    {budget && <dl className="budget-totals">
      <div><dt>{t('Remaining')}</dt><dd>{dollars(budget.remaining_usd)}</dd></div>
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
