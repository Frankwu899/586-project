import type { EvidenceReference, ProductionCreativeBrief, TaskState, TextStoryboard } from './generated/contracts';

export interface ProductionSnapshot {
  state: TaskState;
  brief: ProductionCreativeBrief | null;
  storyboard: TextStoryboard | null;
  historical: boolean;
}

export function currentProduction(state: TaskState): ProductionSnapshot | null {
  const brief = state.production_briefs.find((item) => item.output_id === state.task.current_production_brief?.id && item.revision === state.task.current_production_brief.revision);
  const storyboard = state.storyboards.find((item) => item.output_id === state.task.current_storyboard?.id && item.revision === state.task.current_storyboard.revision);
  if (!brief || !storyboard) return null;
  return { state, brief, storyboard, historical: brief.currentness !== 'current' || storyboard.currentness !== 'current' };
}

export const productionStatus = (snapshot: ProductionSnapshot) => snapshot.historical ? 'HISTORICAL VERSION — does not reflect the latest inputs' : 'Saved production version';
export const escapeHtml = (value: unknown) => String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]!));
const stamp = (value: number) => `${Number(value.toFixed(2))}s`;
const text = (value: unknown) => escapeHtml(value).replace(/\r?\n/g, '<br>');

export function evidenceDescription(state: TaskState, evidence: EvidenceReference): string {
  const analysis = state.analyses.find((item) => item.analysis_id === evidence.analysis_id && item.revision === evidence.analysis_revision);
  const event = analysis?.events.find((item) => item.event_id === evidence.event_id);
  const video = state.videos.find((item) => item.video_id === evidence.video_id);
  const deleted = Boolean(video?.deleted_at);
  const boundaries = video?.frame_timing?.frame_boundaries_seconds;
  const start = event?.start_frame === null || event?.start_frame === undefined ? undefined : boundaries?.[event.start_frame];
  const end = event?.end_frame === null || event?.end_frame === undefined ? undefined : boundaries?.[event.end_frame];
  const timing = start !== undefined && end !== undefined ? `${stamp(start)}–${stamp(end)} · ` : '';
  const observation = event?.text ?? event?.description ?? evidence.event_id;
  const mediaStatus = deleted ? ' · Reference media deleted; playback unavailable' : !video || video.intake_status !== 'ready' ? ' · Reference playback unavailable' : '';
  return `${timing}${observation} — ${evidence.reason} [${evidence.analysis_id} r${evidence.analysis_revision}; ${evidence.video_id}; ${evidence.event_id}]${mediaStatus}`;
}

export function sourceSummary(snapshot: ProductionSnapshot): string {
  const output = snapshot.brief ?? snapshot.storyboard!;
  const analysis = snapshot.state.analyses.find((item) => item.analysis_id === output.analysis_ref.id && item.revision === output.analysis_ref.revision);
  const video = snapshot.state.videos.find((item) => item.video_id === analysis?.video_id);
  const deleted = video?.deleted_at ? ' · Reference media deleted; playback unavailable' : '';
  return `Brand/task inputs ${output.brief_ref.id} r${output.brief_ref.revision} · Analysis ${output.analysis_ref.id} r${output.analysis_ref.revision} · Approved direction ${output.direction_ref.id} r${output.direction_ref.revision}${deleted}`;
}

export function productionFilename(snapshot: ProductionSnapshot, extension: string): string {
  const title = (snapshot.brief?.title ?? snapshot.state.task.title).normalize('NFKC').replace(/[^\p{L}\p{N}_-]+/gu, '-').replace(/^-+|-+$/g, '').slice(0, 80) || 'production';
  const revisions = [snapshot.brief ? `brief-r${snapshot.brief.revision}` : '', snapshot.storyboard ? `storyboard-r${snapshot.storyboard.revision}` : ''].filter(Boolean).join('-');
  return `${title}-${snapshot.historical ? 'historical-' : ''}${revisions}.${extension}`;
}

export function productionHtml(snapshot: ProductionSnapshot): string {
  const { state, brief, storyboard } = snapshot;
  const output = brief ?? storyboard!;
  const input = state.briefs.find((item) => item.brief_id === output.brief_ref.id && item.revision === output.brief_ref.revision);
  const paragraph = (label: string, value: unknown) => `<section class="document-field"><h3>${text(label)}</h3><p>${text(value || 'Not specified')}</p></section>`;
  const citations = (evidence: EvidenceReference[]) => evidence.length ? `<ul class="citations">${evidence.map((item) => `<li>${text(evidenceDescription(state, item))}</li>`).join('')}</ul>` : '<p class="muted">Original production suggestion — no reference citation. Product claims remain limited to confirmed inputs.</p>';
  const title = brief?.title ?? `${state.task.title} — storyboard`;
  return `<!doctype html><html lang="${/[\u3400-\u9fff]/.test(title) ? 'zh' : 'en'}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${escapeHtml(productionFilename(snapshot, 'pdf'))}</title><style>
    @page { size: A4; margin: 17mm 16mm; } * { box-sizing: border-box; } body { font-family: Arial,"Noto Sans CJK SC","Microsoft YaHei",sans-serif; color:#29251f; line-height:1.55; margin:0; padding:30px; background:#fff; font-size:11pt; } main { max-width:820px; margin:auto; } h1,h2 { font-family:Georgia,"Noto Serif CJK SC",serif; line-height:1.2; } h1 { font-size:29pt; margin:14px 0; } h2 { font-size:21pt; padding-top:18px; border-top:1px solid #d8d2c8; } h3 { font-size:11pt; margin:0 0 5px; } p,li { overflow-wrap:anywhere; word-break:normal; } p { margin:0 0 12px; } .eyebrow { text-transform:uppercase; letter-spacing:.16em; color:#955139; font-size:9pt; } .status { padding:10px 12px; border:1px solid #b9afa0; margin:16px 0; font-weight:bold; } .history { background:#fff1dd; } .muted,.provenance { color:#645e55; font-size:9pt; } .provenance { border-top:1px solid #d8d2c8; padding-top:12px; overflow-wrap:anywhere; } .context { display:grid; grid-template-columns:1fr 1fr; gap:0 20px; } .document-field { margin-bottom:16px; } .shot { border-top:1px solid #d8d2c8; padding:16px 0 8px; break-inside:avoid-page; } .shot h3 { font-size:14pt; } .shot dl { display:grid; grid-template-columns:105px 1fr; gap:6px 12px; margin:14px 0; } dt { color:#645e55; } dd { margin:0; white-space:normal; overflow-wrap:anywhere; } .citations { color:#645e55; font-size:9pt; padding-left:18px; } .tag { font-size:9pt; color:#955139; } h1,h2,h3,dt { break-after:avoid; } footer { border-top:1px solid #d8d2c8; padding-top:14px; margin-top:24px; } @media print { body { padding:0; } main { max-width:none; } .storyboard { break-before:page; } .shot { break-inside:avoid-page; } .shot.long-shot { break-inside:auto; } .storyboard > p { break-after:avoid; } } @media(max-width:500px) { body { padding:18px; } .context { display:block; } .shot dl { display:block; } dt { margin-top:8px; } }
  </style></head><body><main><header><p class="eyebrow">Video Anatomy / Production document</p><p>${text(state.task.title)}</p><h1>${text(title)}</h1><p class="status${snapshot.historical ? ' history' : ''}">${text(productionStatus(snapshot))}</p><p class="muted">${text(output.origin.kind)} · ${text(output.origin.description)}</p></header>
  ${input ? `<section><h2>Task context</h2><div class="context">${paragraph('Brand / product', `${input.brand_company} / ${input.product}`)}${paragraph('Audience', input.target_audience)}${paragraph('Communication goal', input.communication_goal)}${paragraph('Platform / planned duration', `${input.platform} · ${input.target_duration_seconds}s`)}</div>${paragraph('Confirmed selling points', input.claim_details.map((item) => `${item.statement}${item.qualification ? ` — ${item.qualification}` : ''}`).join('\n'))}${input.prohibited_claims.length ? paragraph('Do not claim', input.prohibited_claims.join('\n')) : ''}</section>` : ''}
  ${brief ? `<section><h2>Production creative brief</h2><p class="muted">${text(brief.output_id)} · revision ${brief.revision}${brief.edited ? ' · manually edited' : ''}</p>${paragraph('Core message', brief.core_message)}${paragraph('Opening / Hook', brief.hook)}${paragraph('Narrative', brief.narrative)}${paragraph('Call to action', brief.cta)}${paragraph('Production needs and constraints', brief.production_notes.join('\n'))}<h3>Reference connections</h3>${citations(brief.evidence)}</section>` : ''}
  ${storyboard ? `<section class="storyboard"><h2>Text storyboard</h2><p class="muted">${text(storyboard.output_id)} · revision ${storyboard.revision} · ${stamp(storyboard.target_duration_seconds)} planned duration. Shot times belong to the new video; reference citations use the source video’s clock.</p>${storyboard.rows.map((row, index) => `<article class="shot${[row.visual, row.dialogue, row.on_screen_text, row.sound, row.cta].join('').length > 1000 ? ' long-shot' : ''}"><p class="tag">${row.evidence.length ? 'Reference-informed' : 'Original production suggestion'}</p><h3>Shot ${index + 1} / ${stamp(row.start_seconds)}–${stamp(row.end_seconds)}</h3><dl>${[['Picture', row.visual], ['Dialogue', row.dialogue], ['On-screen text', row.on_screen_text], ['Sound', row.sound], ['CTA', row.cta]].map(([label, value]) => `<dt>${text(label)}</dt><dd>${text(value || '—')}</dd>`).join('')}</dl>${citations(row.evidence)}</article>`).join('')}</section>` : ''}
  <footer><p class="provenance">Task ${text(state.task.task_id)}<br>${text(sourceSummary(snapshot))}<br>${brief ? `Brief ${text(brief.output_id)} r${brief.revision} · ` : ''}${storyboard ? `Storyboard ${text(storyboard.output_id)} r${storyboard.revision}` : ''}</p><p class="muted">Saved production draft for team discussion. Reference observations and creative suggestions do not certify product claims or predict performance.</p></footer></main></body></html>`;
}

function csvCell(value: unknown): string {
  let safe = String(value ?? '');
  if (/^[\s\uFEFF]*[=+@-]/.test(safe) || /^[\t\r\n]/.test(safe)) safe = `'${safe}`;
  return `"${safe.replace(/"/g, '""')}"`;
}

export function storyboardCsv(snapshot: ProductionSnapshot): string {
  if (!snapshot.storyboard) throw new Error('This saved snapshot has no storyboard.');
  const story = snapshot.storyboard;
  const rows: unknown[][] = [['task_title', 'status', 'origin', 'output_id', 'revision', 'input_versions', 'row_id', 'planned_start_seconds', 'planned_end_seconds', 'visual', 'dialogue', 'on_screen_text', 'sound', 'cta', 'creative_source', 'reference_evidence']];
  for (const row of story.rows) rows.push([snapshot.state.task.title, productionStatus(snapshot), story.origin.kind, story.output_id, story.revision, sourceSummary(snapshot), row.row_id, row.start_seconds, row.end_seconds, row.visual, row.dialogue, row.on_screen_text, row.sound, row.cta, row.evidence.length ? 'Reference-informed' : 'Original production suggestion', row.evidence.map((item) => evidenceDescription(snapshot.state, item)).join('; ')]);
  return '\uFEFF' + rows.map((row) => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
}

export function productionMarkdown(snapshot: ProductionSnapshot): string {
  const { state, brief, storyboard } = snapshot;
  const clean = (value: unknown) => String(value ?? '').replace(/[&<>]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[character]!)).replace(/[\\`*_{}[\]()#+!|]/g, (character) => `\\${character}`);
  const output = [`# ${clean(brief?.title ?? state.task.title)}`, '', `Task: ${clean(state.task.title)}`, '', productionStatus(snapshot), '', clean(sourceSummary(snapshot)), ''];
  if (brief) {
    output.push(`Production brief ${brief.output_id} r${brief.revision} · ${brief.origin.kind}`, '');
    for (const [label, value] of [['Core message', brief.core_message], ['Hook', brief.hook], ['Narrative', brief.narrative], ['CTA', brief.cta], ['Production needs', brief.production_notes.join('\n')]]) output.push(`## ${label}`, '', clean(value), '');
    output.push('## Reference connections', '', ...brief.evidence.map((item) => clean(evidenceDescription(state, item))), '');
  }
  if (storyboard) {
    output.push(`## Text storyboard — ${storyboard.output_id} r${storyboard.revision}`, '', `Planned duration: ${stamp(storyboard.target_duration_seconds)}`, '');
    for (const [index, row] of storyboard.rows.entries()) output.push(`### Shot ${index + 1} · ${stamp(row.start_seconds)}–${stamp(row.end_seconds)}`, '', `Picture: ${clean(row.visual)}`, '', `Dialogue: ${clean(row.dialogue || '—')}`, '', `On-screen text: ${clean(row.on_screen_text || '—')}`, '', `Sound: ${clean(row.sound || '—')}`, '', `CTA: ${clean(row.cta || '—')}`, '', row.evidence.length ? row.evidence.map((item) => clean(evidenceDescription(state, item))).join('\n') : 'Original production suggestion — no reference citation.', '');
  }
  return output.join('\n');
}
