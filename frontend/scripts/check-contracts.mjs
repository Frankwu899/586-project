import { compileFromFile } from 'json-schema-to-typescript';
import { readFile } from 'node:fs/promises';

const generated = await compileFromFile('../contracts/v0.3.task-state.schema.json');
const saved = await readFile('src/generated/contracts.ts', 'utf8');
if (generated !== saved) {
  console.error('Frontend contracts differ from the authoritative schema. Run npm run contracts:generate.');
  process.exitCode = 1;
}
