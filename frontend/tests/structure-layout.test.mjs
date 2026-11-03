import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/structureLayout.ts', import.meta.url), 'utf8');
const { outputText } = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } });
const { layoutStructure, readableFit, wrapGraphText } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`);
const node = (id, label = id) => ({ id, label, moments: [] });
const edge = (from, to, relation = 'supports the next claim with visible evidence') => ({ id: `${from}-${to}`, from_node: from, to_node: to, relation });
const intersects = (a, b) => a.x < b.x + b.width && a.x + a.width > b.x && a.y < b.y + b.height && a.y + a.height > b.y;
function assertReadableGeometry(layout) {
  const boxes = [...layout.nodes.values(), ...layout.edges.values()];
  for (let i = 0; i < boxes.length; i++) {
    const box = boxes[i];
    assert.ok(box.x >= 0 && box.y >= 0 && box.x + box.width <= layout.width && box.y + box.height <= layout.height, 'content remains inside pannable bounds');
    for (const other of boxes.slice(i + 1)) assert.ok(!intersects(box, other), 'node and relationship text boxes must not overlap');
  }
}

test('a deep graph keeps every relationship and has no four-column clamp', () => {
  const nodes = Array.from({ length: 20 }, (_, i) => node(`n${i}`));
  const edges = nodes.slice(1).map((item, i) => edge(nodes[i].id, item.id));
  const layout = layoutStructure({ nodes, edges });
  assert.equal(layout.nodes.get('n19').level, 19);
  assert.equal(layout.edges.size, edges.length);
  assertReadableGeometry(layout);
});

test('branched, cyclic and long links reserve disjoint labels outside node cards', () => {
  const nodes = Array.from({ length: 20 }, (_, i) => node(`n${i}`, i === 3 ? 'Long observed description '.repeat(18) : `Observation ${i}`));
  const edges = nodes.slice(1).map(item => edge('n0', item.id));
  edges.push(edge('n19', 'n0'), ...nodes.slice(1, 11).map((item, i) => edge(item.id, nodes[i + 2].id, '借助观察到的细节解释产品主张，而不是仅仅按照时间顺序连接节点')));
  const layout = layoutStructure({ nodes, edges });
  assert.equal(layout.edges.size, 30);
  assert.ok(layout.edges.get('n19-n0').outside);
  assert.ok(layout.nodes.get('n3').height > layout.nodes.get('n1').height);
  assertReadableGeometry(layout);
});

test('wrapping preserves long English, Chinese and unbroken identifiers without ellipsis', () => {
  for (const original of ['the relationship preserves the actual explanation '.repeat(8), '同一个产品的可见演示提供具体支持'.repeat(8), 'UnbrokenReference'.repeat(20)]) {
    const lines = wrapGraphText(original, 164, 14);
    assert.ok(lines.length > 1);
    assert.equal(lines.join('').replaceAll(/\s/gu, ''), original.replaceAll(/\s/gu, ''));
    assert.ok(!lines.join('').includes('…'));
  }
});

test('automatic fit never shrinks below the readable scale, including narrow windows', () => {
  for (const [width, height] of [[1440, 900], [1024, 768], [390, 844]]) {
    assert.equal(readableFit(width, height, 4800, 2200), 1);
    assert.ok(readableFit(width, height, 240, 140) >= 1);
    assert.ok(readableFit(width, height, 240, 140) <= 1.25);
  }
});
