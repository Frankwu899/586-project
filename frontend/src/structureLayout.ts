import type { StructureGraph } from './structureApi';

export type TextMeasure = (text: string, size: number) => number;
type Box = { x: number; y: number; width: number; height: number };
export type GraphNodeLayout = Box & { lines: string[]; level: number };
export type GraphEdgeLayout = Box & { lines: string[]; path: string; outside: boolean };
const fallbackMeasure: TextMeasure = (text, size) => [...text].reduce((width, char) => width + (char.charCodeAt(0) > 255 ? size : size * .6), 0);

/** Break at words where possible, and at characters for CJK or very long words. */
export function wrapGraphText(text: string, width: number, size: number, measure = fallbackMeasure): string[] {
  const lines: string[] = [];
  for (const paragraph of text.split('\n')) {
    let line = '';
    for (const token of paragraph.match(/\S+\s*|\s+/gu) ?? ['']) {
      if (line && measure(line + token.trimEnd(), size) > width) { lines.push(line.trimEnd()); line = ''; }
      for (const char of token) {
        if (!line && /\s/u.test(char)) continue;
        if (line && measure(line + char, size) > width) { lines.push(line.trimEnd()); line = ''; }
        line += char;
      }
    }
    if (line.trim() || !lines.length) lines.push(line.trimEnd());
  }
  return lines;
}

/** A bounded layered layout. Back/cycle and skipped-level edges use outside lanes. */
export function layoutStructure(graph: StructureGraph, measure: TextMeasure = fallbackMeasure) {
  const nodeWidth = 224;
  const nodes = new Map<string, GraphNodeLayout>();
  const edges = new Map<string, GraphEdgeLayout>();
  const visited = new Set<string>();
  const active = new Set<string>();
  const backEdges = new Set<string>();
  const order: string[] = [];
  const outgoing = new Map(graph.nodes.map(node => [node.id, graph.edges.filter(edge => edge.from_node === node.id)]));
  function visit(id: string) {
    if (visited.has(id)) return;
    visited.add(id); active.add(id);
    for (const edge of outgoing.get(id) ?? []) {
      if (active.has(edge.to_node)) backEdges.add(edge.id);
      else visit(edge.to_node);
    }
    active.delete(id); order.unshift(id);
  }
  // Start with source nodes so a disconnected cycle cannot push a source backward.
  for (const node of graph.nodes.filter(node => !graph.edges.some(edge => edge.to_node === node.id))) visit(node.id);
  for (const node of graph.nodes) visit(node.id);
  const levels = new Map(graph.nodes.map(node => [node.id, 0]));
  for (const id of order) for (const edge of outgoing.get(id) ?? []) {
    if (!backEdges.has(edge.id)) levels.set(edge.to_node, Math.max(levels.get(edge.to_node) ?? 0, (levels.get(id) ?? 0) + 1));
  }
  const layerCount = Math.max(0, ...levels.values()) + 1;
  const layers = Array.from({ length: layerCount }, () => [] as string[]);
  for (const node of graph.nodes) layers[levels.get(node.id)!].push(node.id);
  // Stable predecessor ordering reduces crossings without changing graph semantics.
  for (let level = 1; level < layers.length; level++) {
    const rank = (id: string) => {
      const parents = graph.edges.filter(edge => edge.to_node === id && levels.get(edge.from_node) === level - 1);
      return parents.length ? parents.reduce((sum, edge) => sum + layers[level - 1].indexOf(edge.from_node), 0) / parents.length : graph.nodes.findIndex(node => node.id === id);
    };
    layers[level].sort((a, b) => rank(a) - rank(b));
  }
  for (const edge of graph.edges) {
    const width = Math.max(104, Math.min(180, measure(edge.relation, 14) + 16));
    const lines = wrapGraphText(edge.relation, width - 16, 14, measure);
    edges.set(edge.id, { x: 0, y: 0, width, height: lines.length * 20 + 12, lines, path: '', outside: levels.get(edge.to_node)! !== levels.get(edge.from_node)! + 1 });
  }
  const gaps = layers.map((_, level) => Math.max(52, ...graph.edges.filter(edge => levels.get(edge.from_node) === level && !edges.get(edge.id)!.outside).map(edge => edges.get(edge.id)!.width + 40)));
  const columnX = [24];
  for (let level = 1; level < layers.length; level++) columnX[level] = columnX[level - 1] + nodeWidth + gaps[level - 1];
  for (const [level, ids] of layers.entries()) {
    let y = 24;
    for (const id of ids) {
      const node = graph.nodes.find(item => item.id === id)!;
      const lines = wrapGraphText(node.label, nodeWidth - 32, 16, measure);
      // Metadata stays separate and wraps too; titles never get a nested scrollbar.
      const timeRows = Math.max(1, Math.ceil(node.moments.length / 4));
      const height = 66 + lines.length * 23 + timeRows * 17;
      nodes.set(id, { x: columnX[level], y, width: nodeWidth, height, lines, level });
      y += height + 44;
    }
  }
  let height = Math.max(0, ...[...nodes.values()].map(node => node.y + node.height)) + 24;
  // Center short columns against the tallest one.
  for (const ids of layers) {
    const bottom = Math.max(0, ...ids.map(id => nodes.get(id)!.y + nodes.get(id)!.height));
    for (const id of ids) nodes.get(id)!.y += Math.max(0, (height - 24 - bottom) / 2);
  }
  // Reserve non-overlapping label boxes in each inter-column gap.
  for (let level = 0; level < layers.length - 1; level++) {
    const links = graph.edges.filter(edge => levels.get(edge.from_node) === level && !edges.get(edge.id)!.outside);
    const desired = (id: string) => { const node = nodes.get(id)!; return node.y + node.height / 2; };
    links.sort((a, b) => desired(a.from_node) + desired(a.to_node) - desired(b.from_node) - desired(b.to_node));
    let bottom = 16;
    for (const edge of links) {
      const box = edges.get(edge.id)!;
      const from = nodes.get(edge.from_node)!; const to = nodes.get(edge.to_node)!;
      box.x = from.x + from.width + (gaps[level] - box.width) / 2;
      box.y = Math.max(bottom + 12, (desired(edge.from_node) + desired(edge.to_node)) / 2 - box.height / 2);
      bottom = box.y + box.height;
      const middleX = box.x + box.width / 2; const middleY = box.y + box.height / 2;
      box.path = `M${from.x + from.width},${desired(edge.from_node)} C${middleX},${desired(edge.from_node)} ${from.x + from.width + 12},${middleY} ${middleX},${middleY} S${middleX},${desired(edge.to_node)} ${to.x},${desired(edge.to_node)}`;
      height = Math.max(height, bottom + 24);
    }
  }
  // Route long/cyclic edges below the nodes in separate lanes. This avoids paths
  // through intermediate node cards, and makes every relationship readable.
  const width = (columnX.at(-1) ?? 24) + nodeWidth + 24;
  let laneY = height + 12;
  for (const edge of graph.edges.filter(edge => edges.get(edge.id)!.outside)) {
    const box = edges.get(edge.id)!; const from = nodes.get(edge.from_node)!; const to = nodes.get(edge.to_node)!;
    box.x = Math.max(24, Math.min(width - box.width - 24, (from.x + to.x + nodeWidth - box.width) / 2));
    box.y = laneY;
    const y = laneY + box.height / 2;
    const startX = from.x + from.width; const endX = to.x;
    box.path = `M${startX},${from.y + from.height / 2} L${startX + 12},${from.y + from.height / 2} L${startX + 12},${y} L${endX - 12},${y} L${endX - 12},${to.y + to.height / 2} L${endX},${to.y + to.height / 2}`;
    laneY += box.height + 22;
  }
  return { nodes, edges, width, height: Math.max(height, laneY + 12) };
}

export function readableFit(width: number, height: number, graphWidth: number, graphHeight: number) {
  return Math.max(1, Math.min(1.25, (width - 24) / graphWidth, (height - 24) / graphHeight));
}
