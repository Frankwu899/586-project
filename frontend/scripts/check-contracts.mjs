import { generateContracts } from './generate-contracts.mjs';
import { readFile } from 'node:fs/promises';

const generated = await generateContracts();
const saved = await readFile('src/generated/contracts.ts', 'utf8');
if (generated !== saved) {
  console.error('Frontend contracts differ from the authoritative schema. Run npm run contracts:generate.');
  process.exitCode = 1;
}
