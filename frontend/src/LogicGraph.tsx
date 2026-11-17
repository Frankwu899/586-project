import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useI18n } from './i18n';
import type { StructureGraph, StructureNode } from './structureApi';
import { layoutStructure, readableFit } from './structureLayout';

const kinds: Record<StructureNode['kind'], string> = { observation: 'Video observation', source_claim: 'Attributed claim', inference: 'Inference', user_context: 'Your context' };
const time = (seconds: number) => `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${Math.floor(seconds % 60).toString().padStart(2, '0')}`;

export default function LogicGraph({ graph, selected, onSelect, chosen, initialFit = false }: { graph: StructureGraph; selected: string | null; onSelect: (id: string) => void; chosen: string[]; initialFit?: boolean }) {
  const { t } = useI18n();
  const markerId = useId().replaceAll(':', '');
  const viewport = useRef<HTMLDivElement>(null);
  const zoomRef = useRef(1);
  const [zoom, setZoom] = useState(1);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const drag = useRef<{ x: number; y: number; left: number; top: number } | null>(null);
  const initialized = useRef(false);
  const layout = useMemo(() => {
    const context = document.createElement('canvas').getContext('2d');
    return layoutStructure(graph, context ? (text, fontSize) => { context.font = `${fontSize === 16 ? '600 ' : ''}${fontSize}px system-ui, sans-serif`; return context.measureText(text).width; } : undefined);
  }, [graph]);
  const offset = { x: Math.max(0, (size.width - layout.width * zoom) / 2), y: Math.max(0, (size.height - layout.height * zoom) / 2) };

  const changeZoom = useCallback((next: number, anchor?: { x: number; y: number }) => {
    const element = viewport.current;
    if (!element) return;
    next = Math.max(.5, Math.min(2, next));
    const point = anchor ?? { x: element.clientWidth / 2, y: element.clientHeight / 2 };
    const oldOffsetX = Math.max(0, (element.clientWidth - layout.width * zoomRef.current) / 2);
    const oldOffsetY = Math.max(0, (element.clientHeight - layout.height * zoomRef.current) / 2);
    const worldX = (element.scrollLeft + point.x - oldOffsetX) / zoomRef.current;
    const worldY = (element.scrollTop + point.y - oldOffsetY) / zoomRef.current;
    zoomRef.current = next; setZoom(next);
    requestAnimationFrame(() => element.scrollTo({ left: worldX * next + Math.max(0, (element.clientWidth - layout.width * next) / 2) - point.x, top: worldY * next + Math.max(0, (element.clientHeight - layout.height * next) / 2) - point.y }));
  }, [layout.width, layout.height]);

  const reset = (fit = false) => {
    const element = viewport.current;
    if (!element) return;
    const next = fit ? readableFit(element.clientWidth, element.clientHeight, layout.width, layout.height) : 1;
    changeZoom(next);
    const node = layout.nodes.get(selected ?? graph.nodes[0]?.id);
    requestAnimationFrame(() => element.scrollTo({ left: node ? Math.max(0, (node.x + node.width / 2) * next - element.clientWidth / 2) : 0, top: node ? Math.max(0, (node.y + node.height / 2) * next - element.clientHeight / 2) : 0 }));
  };

  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    // Native scrolling keeps the user's location on resize; observe only the
    // container size for centering. Never fit again because a drawer opened.
    const observer = new ResizeObserver(() => setSize({ width: element.clientWidth, height: element.clientHeight }));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (initialized.current || !size.width || !size.height || !viewport.current) return;
    initialized.current = true;
    const fitted = initialFit ? readableFit(size.width, size.height, layout.width, layout.height) : 1;
    if (initialFit) changeZoom(fitted);
    const first = layout.nodes.get(selected ?? graph.nodes[0]?.id);
    if (first && initialFit) requestAnimationFrame(() => viewport.current?.scrollTo({ left: Math.max(0, (first.x + first.width / 2) * fitted - size.width / 2), top: Math.max(0, (first.y + first.height / 2) * fitted - size.height / 2) }));
    else if (first) viewport.current.scrollTo({ left: Math.max(0, first.x + first.width / 2 - size.width / 2), top: Math.max(0, first.y + first.height / 2 - size.height / 2) });
  }, [size, layout, selected, graph.nodes, initialFit, changeZoom]);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const onWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const bounds = element.getBoundingClientRect();
      changeZoom(zoomRef.current * Math.exp(-event.deltaY * .005), { x: event.clientX - bounds.left, y: event.clientY - bounds.top });
    };
    element.addEventListener('wheel', onWheel, { passive: false });
    return () => element.removeEventListener('wheel', onWheel);
  }, [changeZoom]);

  return <div className="logic-graph">
    <div className="logic-controls" role="group" aria-label={t('Graph navigation')}>
      <button type="button" className="secondary" aria-label={t('Zoom out')} disabled={zoom <= .5} onClick={() => changeZoom(zoom - .1)}>−</button>
      <button type="button" className="secondary logic-zoom" aria-label={t('Set zoom to 100%')} onClick={() => changeZoom(1)}>{Math.round(zoom * 100)}%</button>
      <button type="button" className="secondary" aria-label={t('Zoom in')} disabled={zoom >= 2} onClick={() => changeZoom(zoom + .1)}>+</button>
      <button type="button" className="secondary" title={t('Fit at a readable size; pan if the graph is larger than the view.')} onClick={() => reset(true)}>{t('Fit')}</button>
      <button type="button" className="secondary" onClick={() => reset()}>{t('Reset view')}</button>
    </div>
    <div ref={viewport} className="logic-viewport" style={{ height: `clamp(280px, ${layout.height * zoom + 24}px, max(360px, 60dvh))` }} tabIndex={0} role="region" aria-label={t('Video logic graph. Scroll to explore, or use Tab to select a node.')} onKeyDown={(event) => {
      if (event.target !== event.currentTarget || event.ctrlKey || event.metaKey) return;
      const moves: Record<string, [number, number]> = { ArrowLeft: [-80, 0], ArrowRight: [80, 0], ArrowUp: [0, -80], ArrowDown: [0, 80], PageUp: [0, -event.currentTarget.clientHeight * .8], PageDown: [0, event.currentTarget.clientHeight * .8] };
      if (moves[event.key]) { event.preventDefault(); event.currentTarget.scrollBy(...moves[event.key]); }
      else if (['+', '=', '-'].includes(event.key)) { event.preventDefault(); changeZoom(zoom + (event.key === '-' ? -.1 : .1)); }
      else if (event.key === 'Home' || event.key === '0') { event.preventDefault(); reset(); }
    }} onPointerDown={(event) => {
      if (event.pointerType === 'touch' || event.button !== 0 || (event.target as HTMLElement).closest('button')) return;
      const element = event.currentTarget;
      drag.current = { x: event.clientX, y: event.clientY, left: element.scrollLeft, top: element.scrollTop };
      element.setPointerCapture(event.pointerId); element.focus({ preventScroll: true });
    }} onPointerMove={(event) => {
      if (!drag.current) return;
      event.currentTarget.scrollTo(drag.current.left + drag.current.x - event.clientX, drag.current.top + drag.current.y - event.clientY);
    }} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
      <div className="logic-scroll-space" style={{ width: Math.max(size.width, layout.width * zoom), height: Math.max(size.height, layout.height * zoom) }}>
        <div className="logic-canvas" style={{ width: layout.width, height: layout.height, left: offset.x, top: offset.y, transform: `scale(${zoom})` }}>
          <svg width={layout.width} height={layout.height} className="logic-connections" aria-hidden="true"><defs><marker id={markerId} markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7" fill="currentColor" /></marker></defs>{graph.edges.map(edge => <path key={edge.id} d={layout.edges.get(edge.id)!.path} fill="none" stroke="currentColor" strokeWidth="1.5" markerEnd={`url(#${markerId})`} />)}</svg>
          {graph.edges.map(edge => { const box = layout.edges.get(edge.id)!; return <div key={edge.id} className="logic-edge-label" aria-hidden="true" style={{ left: box.x, top: box.y, width: box.width, minHeight: box.height }}>{box.lines.map((line, index) => <span key={index}>{line}</span>)}</div>; })}
          {graph.nodes.map(node => { const box = layout.nodes.get(node.id)!; return <button data-node-id={node.id} key={node.id} type="button" className={`logic-node ${node.kind} ${node.id === selected ? 'selected' : ''}`} style={{ left: box.x, top: box.y, width: box.width, minHeight: box.height }} onClick={() => onSelect(node.id)} aria-pressed={node.id === selected}>
            <span className="node-kind">{t(kinds[node.kind])}{chosen.includes(node.id) ? ' ✓' : ''}</span><strong>{box.lines.map((line, index) => <span key={index}>{line}</span>)}</strong><span className="node-time">{node.moments.length ? [...new Set(node.moments.map(moment => time(moment.start_seconds)))].join(' · ') : t('Background context')}</span>
          </button>; })}
        </div>
      </div>
    </div>
    <details className="logic-relationships"><summary>{t('Connections')} · {graph.edges.length}</summary><ol>{graph.edges.map(edge => <li key={edge.id}><div><button type="button" className="text-button" onClick={() => onSelect(edge.from_node)}>{graph.nodes.find(node => node.id === edge.from_node)?.label}</button><span className="logic-list-relation">{edge.relation} →</span><button type="button" className="text-button" onClick={() => onSelect(edge.to_node)}>{graph.nodes.find(node => node.id === edge.to_node)?.label}</button></div><p>{edge.explanation}</p></li>)}</ol></details>
  </div>;
}
