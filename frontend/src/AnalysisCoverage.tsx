import type { AnalysisResult, EvidenceEvent } from './generated/contracts';
import { useI18n } from './i18n';
import './researchTranslations';
import { ConnectionHelp } from './ApiConnection';

export const researchChannels = ['visual_action', 'on_screen_text', 'speech'] as const;
export const channelLabels = { visual_action: 'Visuals', on_screen_text: 'Visible text', speech: 'Speech' };
export function incompleteChannels(analysis: AnalysisResult) {
  return researchChannels.filter((kind) => ['failed', 'not_analyzed'].includes(analysis.coverage[kind]) || analysis.extraction_failures?.[kind]);
}
export function retryableChannels(analysis: AnalysisResult) {
  return incompleteChannels(analysis);
}

export function EmptyChannel({ analysis, kind }: { analysis: AnalysisResult; kind: EvidenceEvent['kind'] }) {
  const { t } = useI18n();
  const state = analysis.coverage[kind];
  const failure = analysis.extraction_failures?.[kind as typeof researchChannels[number]];
  return <span className={`timeline-channel-state ${state}`} title={failure?.message}>
    {t(failure || state === 'failed' ? 'Failed to extract' : state === 'not_analyzed' ? kind === 'speech' ? 'Speech has not been transcribed for this analysis.' : 'Not checked' : state === 'none_found' ? 'No observations detected' : 'Some results are available; extraction is incomplete.')}
  </span>;
}

export default function AnalysisCoverage({ analysis, onRetry, busy }: { analysis: AnalysisResult; onRetry?: () => void; busy: boolean }) {
  const { t } = useI18n();
  const incomplete = incompleteChannels(analysis);
  if (!incomplete.length) return null;
  return <section className="analysis-channel-status" aria-label={t('Coverage and source')}>
    <p><strong>{t('Analysis incomplete')}</strong></p>
    <ul>{incomplete.map((kind) => <li key={kind}>
      <strong>{t(channelLabels[kind])}</strong>
      <span>{analysis.extraction_failures?.[kind]?.message ?? t(analysis.coverage[kind] === 'failed' ? 'Extraction failed' : kind === 'speech' ? 'Speech has not been transcribed for this analysis.' : 'Not analyzed')}</span>
    </li>)}</ul>
    <ConnectionHelp message={incomplete.map((kind) => analysis.extraction_failures?.[kind]?.message ?? '').join(' ')} />
    {onRetry && retryableChannels(analysis).length > 0 && <button type="button" className="secondary" disabled={busy} onClick={onRetry}>{t('Retry missing analysis')}</button>}
  </section>;
}
