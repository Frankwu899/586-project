import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';
const source = await readFile(new URL('../src/productionExports.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { currentProduction, productionHtml, storyboardCsv, productionMarkdown, productionFilename } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const fixture = JSON.parse(await readFile(new URL('../../examples/v0.6.sample-task.json', import.meta.url), 'utf8'));
const snapshot = () => currentProduction(structuredClone(fixture));

test('exports use exact current pointers, not last array entries or matching revision guesses', () => {
  const saved = snapshot();
  assert.ok(saved?.brief && saved.storyboard);
  const state = structuredClone(fixture);
  state.production_briefs.push({ ...saved.brief, output_id: 'unrelated', revision: 999, title: 'DO NOT EXPORT' });
  state.storyboards.push({ ...saved.storyboard, output_id: 'other-story', revision: 999 });
  const html = productionHtml(currentProduction(state));
  assert.doesNotMatch(html, /DO NOT EXPORT|other-story/);
  assert.match(html, new RegExp(saved.brief.output_id));
  assert.match(html, new RegExp(saved.storyboard.output_id));
});
test('historical exports identify exact versions, deleted media and original shots in every format', () => {
  const saved = snapshot(); saved.historical = true;
  saved.state.videos[0].deleted_at = '2026-10-17T20:00:00Z';
  saved.storyboard.rows[0].evidence = [];
  for (const result of [productionHtml(saved), storyboardCsv(saved), productionMarkdown(saved)]) {
    assert.match(result, /HISTORICAL VERSION/); assert.match(result, /Reference media deleted/); assert.match(result, /Original production suggestion/);
  }
  assert.match(productionFilename(saved, 'pdf'), /historical-.*\.pdf$/);
});
test('print treats rich-looking user text as text and preserves mixed-language content', () => {
  const saved = snapshot(); saved.brief.title = '<script>window.hacked=true</script> 中文 & “quoted”';
  saved.storyboard.rows[0].visual = '通勤包 close-up\n下一帧 <img src=x onerror=alert(1)>';
  const html = productionHtml(saved);
  assert.doesNotMatch(html, /<script>|<img src=/); assert.match(html, /&lt;script&gt;/); assert.match(html, /中文 &amp;/);
  assert.match(html, /通勤包 close-up<br>下一帧/); assert.match(html, /break-inside:avoid-page/);
});
test('CSV protects spreadsheet formulas, quotes multiline content and retains Chinese', () => {
  const saved = snapshot(); saved.storyboard.rows[0].dialogue = '=HYPERLINK("https://invalid.test")'; saved.storyboard.rows[0].visual = '中文, "杯子"\n第二行';
  const csv = storyboardCsv(saved);
  assert.ok(csv.startsWith('\uFEFF')); assert.match(csv, /"'=HYPERLINK\(""https:\/\/invalid.test""\)"/); assert.match(csv, /"中文, ""杯子""\n第二行"/);
});
test('legacy artifact history never invents paired storyboard or brief', () => {
  const saved = snapshot(); const briefOnly = { ...saved, storyboard: null, historical: true }; const storyOnly = { ...saved, brief: null, historical: true };
  assert.doesNotMatch(productionHtml(briefOnly), /<h2>Text storyboard<\/h2>/); assert.doesNotMatch(productionHtml(storyOnly), /<h2>Production creative brief<\/h2>/);
  assert.throws(() => storyboardCsv(briefOnly), /no storyboard/);
});

test('Markdown retains literal user wording rather than turning it into headings or links', () => {
  const saved = snapshot(); saved.brief.title = '# Team [plan](https://example.com)'; saved.brief.hook = '**Do not bold this** <script>';
  const markdown = productionMarkdown(saved);
  assert.ok(markdown.includes('\\# Team \\[plan\\]\\(https://example.com\\)'));
  assert.ok(markdown.includes('\\*\\*Do not bold this\\*\\* &lt;script&gt;'));
});
