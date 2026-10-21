import { compile } from 'json-schema-to-typescript';
import { readFile, writeFile } from 'node:fs/promises';

// json-schema-to-typescript cannot represent JSON Schema conditionals. Keep
// them in the authoritative schema/runtime validators, but omit only those
// clauses in the input used to generate structural TypeScript declarations.
function structuralSchema(value) {
  if (Array.isArray(value)) return value.map(structuralSchema);
  if (!value || typeof value !== 'object') return value;
  return Object.fromEntries(Object.entries(value).flatMap(([key, item]) => {
    if (['if', 'then', 'else'].includes(key)) return [];
    if (key === 'allOf') {
      const clauses = item.filter((clause) => !('if' in clause));
      return clauses.length ? [[key, structuralSchema(clauses)]] : [];
    }
    return [[key, structuralSchema(item)]];
  }));
}

export async function generateContracts() {
  const schema = JSON.parse(await readFile('../contracts/v0.7.m2.schema.json', 'utf8'));
  const editors = JSON.parse(await readFile('../contracts/v0.7.editors.schema.json', 'utf8'));
  schema.$defs = { ...schema.$defs, ...editors.$defs };
  for (const [name, property] of Object.entries(editors.properties)) {
    schema.properties[`editor_${name}`] = property;
    schema.required.push(`editor_${name}`);
  }
  return compile(structuralSchema(schema), 'M2ContractBundle');
}

if (process.argv.includes('--write')) {
  await writeFile('src/generated/contracts.ts', await generateContracts());
}
