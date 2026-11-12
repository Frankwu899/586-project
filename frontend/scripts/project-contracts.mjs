import { compile } from 'json-schema-to-typescript';
import { readFile, writeFile, mkdir } from 'node:fs/promises';

const schema = JSON.parse(await readFile(new URL('../../contracts/v1.8.project.schema.json', import.meta.url), 'utf8'));
const generated = await compile(schema, 'Project', { bannerComment: '/* Generated from contracts/v1.8.project.schema.json. Do not edit. */', additionalProperties: false });
const output = new URL('../src/project/contracts.ts', import.meta.url);
if (process.argv.includes('--check')) {
  if (await readFile(output, 'utf8') !== generated) throw new Error('Project types are stale; run npm run project-contracts:generate');
} else {
  await mkdir(new URL('../src/project/', import.meta.url), { recursive: true });
  await writeFile(output, generated);
}
