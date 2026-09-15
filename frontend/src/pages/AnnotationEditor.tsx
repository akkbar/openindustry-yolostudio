import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from 'react';
import { ApiError, getAnnotations, removeAnnotation, saveAnnotation, type AnnotationBox, type AnnotationState } from '../api';
import Dialog from '../components/Dialog';
import { APP_LOCALE, en } from '../locales/en';
import { useProjectClasses } from '../state/ProjectClasses';

const copy = en.annotator;
const number = (value: number) => new Intl.NumberFormat(APP_LOCALE, { maximumFractionDigits: 0 }).format(value);
const clamp = (value: number, min = 0, max = 1) => Math.min(max, Math.max(min, value));
type Pending = { box: AnnotationBox; action: 'create' | 'update' | 'delete'; revision: number };
type Gesture = { kind: 'draw' | 'move' | 'resize' | 'pan'; x: number; y: number; box?: AnnotationBox; handle?: string; panX?: number; panY?: number };

export default function AnnotationEditor({ projectId, initialImageId, onClose }: { projectId: string; initialImageId: string; onClose: () => void }) {
  const classes = useProjectClasses();
  const [imageId, setImageId] = useState(initialImageId);
  const [state, setState] = useState<AnnotationState | null>(null);
  const [boxes, setBoxes] = useState<AnnotationBox[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [mode, setMode] = useState<'draw' | 'select' | 'pan'>('draw');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [reload, setReload] = useState(0);
  const [ready, setReady] = useState(false);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [size, setSize] = useState({ width: 1, height: 1 });
  const [dragging, setDragging] = useState(false);
  const viewport = useRef<HTMLDivElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const draft = useRef<AnnotationBox | null>(null);
  const locked = useRef(false);
  const alive = useRef(true);
  const current = useRef(imageId);
  const blocked = loading || saving || Boolean(pending) || dragging;
  const editingBlocked = blocked || !ready || Boolean(error) || classes.busy || classes.loading;
  const active = classes.selectedClass;
  const fit = state ? Math.min(size.width / state.image.width, size.height / state.image.height) * .96 : 1;
  const displayWidth = (state?.image.width ?? 1) * fit * zoom;
  const displayHeight = (state?.image.height ?? 1) * fit * zoom;
  const left = (size.width - displayWidth) / 2 + pan.x;
  const top = (size.height - displayHeight) / 2 + pan.y;
  const selectedBox = boxes.find(box => box.id === selected);

  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    const element = viewport.current!;
    const observer = new ResizeObserver(entries => setSize({ width: entries[0].contentRect.width, height: entries[0].contentRect.height }));
    observer.observe(element);
    const preventScroll = (event: WheelEvent) => event.preventDefault();
    element.addEventListener('wheel', preventScroll, { passive: false });
    return () => { observer.disconnect(); element.removeEventListener('wheel', preventScroll); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    current.current = imageId;
    setLoading(true); setError(null); setState(null); setBoxes([]); setReady(false); setSelected(null); setPending(null); setZoom(1); setPan({ x: 0, y: 0 });
    void getAnnotations(projectId, imageId, controller.signal).then(result => {
      if (!controller.signal.aborted) { setState(result); setBoxes(result.annotations); setLoading(false); }
    }).catch(failure => { if (!controller.signal.aborted) { setError(failure instanceof ApiError ? failure.message : en.connectionFailure); setLoading(false); } });
    return () => controller.abort();
  }, [imageId, projectId, reload]);
  useEffect(() => {
    if (!pending && !saving) return;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = copy.leaveWarning; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [pending, saving]);

  const commit = async (change: Pending) => {
    if (locked.current) return;
    locked.current = true; setSaving(true); setPending(change); setError(null);
    try {
      const result = change.action === 'delete'
        ? await removeAnnotation(projectId, imageId, change.box.id, change.revision)
        : await saveAnnotation(projectId, imageId, change.box, change.revision, change.action === 'create');
      if (alive.current && current.current === imageId) { setState(result); setBoxes(result.annotations); setPending(null); }
    } catch (failure) {
      if (alive.current) setError(failure instanceof ApiError ? failure.message : en.connectionFailure);
    } finally { locked.current = false; if (alive.current) setSaving(false); }
  };
  const reloadSaved = () => {
    if (pending && !window.confirm(copy.reloadConfirm)) return;
    setPending(null); setReload(value => value + 1);
  };
  const go = (id: string | null) => { if (id && !blocked && !locked.current) setImageId(id); };
  const removeSelected = () => {
    if (!state || !selectedBox || editingBlocked || locked.current) return;
    setBoxes(previous => previous.filter(box => box.id !== selectedBox.id)); setSelected(null);
    void commit({ box: selectedBox, action: 'delete', revision: state.revision });
  };
  useEffect(() => {
    const keydown = (event: KeyboardEvent) => {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || (event.target as Element)?.closest('input, textarea, select, [contenteditable="true"]')) return;
      if (event.key === 'Escape' && gesture.current) {
        event.preventDefault(); gesture.current = null; draft.current = null; setDragging(false); setBoxes(state?.annotations ?? []); setSelected(null); return;
      }
      const key = event.key.toLowerCase();
      if (!['a', 'd', 'delete', '1', '2', '3', '4', '5', '6', '7', '8', '9'].includes(key)) return;
      event.preventDefault();
      if (blocked || locked.current || classes.busy || classes.loading) return;
      if (key === 'a') go(state?.previous_image_id ?? null);
      else if (key === 'd') go(state?.next_image_id ?? null);
      else if (key === 'delete') removeSelected();
      else {
        const definition = classes.data?.classes[Number(key) - 1];
        if (definition) void classes.select(definition.id);
      }
    };
    document.addEventListener('keydown', keydown);
    return () => document.removeEventListener('keydown', keydown);
  });
  const changeZoom = (value: number, anchorX = size.width / 2, anchorY = size.height / 2) => {
    if (dragging || !ready) return;
    const next = clamp(value, .25, 12);
    const ratio = next / zoom;
    setPan({ x: (pan.x + size.width / 2 - anchorX) * ratio + anchorX - size.width / 2, y: (pan.y + size.height / 2 - anchorY) * ratio + anchorY - size.height / 2 });
    setZoom(next);
  };
  const point = (event: ReactPointerEvent) => {
    const bounds = viewport.current!.getBoundingClientRect();
    return { x: (event.clientX - bounds.left - left) / displayWidth, y: (event.clientY - bounds.top - top) / displayHeight };
  };
  const start = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (editingBlocked || locked.current || (event.button !== 0 && event.button !== 1)) return;
    event.preventDefault(); event.currentTarget.focus();
    const p = point(event);
    const target = (event.target as Element).closest('[data-box-id]');
    const box = boxes.find(item => item.id === target?.getAttribute('data-box-id'));
    const handle = (event.target as Element).getAttribute('data-handle');
    if (event.button === 1 || mode === 'pan') gesture.current = { kind: 'pan', x: event.clientX, y: event.clientY, panX: pan.x, panY: pan.y };
    else if (box && (mode === 'select' || handle)) {
      setSelected(box.id); draft.current = box;
      gesture.current = { kind: handle ? 'resize' : 'move', x: p.x, y: p.y, box: { ...box }, handle: handle ?? undefined };
    } else if (mode === 'draw' && active && p.x >= 0 && p.x <= 1 && p.y >= 0 && p.y <= 1) {
      const box: AnnotationBox = { id: crypto.randomUUID().replaceAll('-', ''), image_id: imageId, class_id: active.id, center_x: p.x, center_y: p.y, width: 0, height: 0 };
      draft.current = box; gesture.current = { kind: 'draw', x: p.x, y: p.y, box };
      setSelected(box.id); setBoxes(previous => [...previous, box]);
    } else { setSelected(box?.id ?? null); return; }
    setDragging(true); event.currentTarget.setPointerCapture(event.pointerId);
  };
  const move = (event: ReactPointerEvent<HTMLDivElement>) => {
    const g = gesture.current;
    if (!g) return;
    if (g.kind === 'pan') { setPan({ x: g.panX! + event.clientX - g.x, y: g.panY! + event.clientY - g.y }); return; }
    const p = point(event); const original = g.box!;
    let box = { ...original };
    if (g.kind === 'move') {
      box.center_x = clamp(original.center_x + p.x - g.x, original.width / 2, 1 - original.width / 2);
      box.center_y = clamp(original.center_y + p.y - g.y, original.height / 2, 1 - original.height / 2);
    } else {
      const anchorX = g.kind === 'draw' ? g.x : original.center_x + (g.handle!.includes('w') ? 1 : -1) * original.width / 2;
      const anchorY = g.kind === 'draw' ? g.y : original.center_y + (g.handle!.includes('n') ? 1 : -1) * original.height / 2;
      const x = clamp(p.x), y = clamp(p.y);
      box = { ...box, center_x: (anchorX + x) / 2, center_y: (anchorY + y) / 2, width: Math.abs(x - anchorX), height: Math.abs(y - anchorY) };
    }
    draft.current = box; setBoxes(previous => previous.map(item => item.id === box.id ? box : item));
  };
  const finish = (event: ReactPointerEvent<HTMLDivElement>, cancel = false) => {
    const g = gesture.current; gesture.current = null; setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    if (!g || g.kind === 'pan' || !state) return;
    const box = draft.current!; draft.current = null;
    if (cancel || box.width * state.image.width < 1 || box.height * state.image.height < 1) {
      setBoxes(state.annotations); if (g.kind === 'draw') setSelected(null); return;
    }
    if (g.kind === 'move' && box.center_x === g.box!.center_x && box.center_y === g.box!.center_y) return;
    void commit({ box, action: g.kind === 'draw' ? 'create' : 'update', revision: state.revision });
  };

  return <Dialog title={copy.title} className="annotation-dialog" busy={blocked} onClose={() => { if (!blocked) onClose(); }}>
    <div className="annotation-toolbar">
      <button className="ghost-button" disabled={blocked || !state?.previous_image_id} onClick={() => go(state?.previous_image_id ?? null)}>{copy.previous}</button>
      <button className="ghost-button" disabled={blocked || !state?.next_image_id} onClick={() => go(state?.next_image_id ?? null)}>{copy.next}</button>
      <span>{state && copy.position(number(state.position), number(state.total))}</span>
      <strong className="annotation-progress">{state && copy.progress(number(state.annotated_count), number(state.total))}</strong>
      <button className="primary-button" disabled={blocked} onClick={onClose}>{copy.close}</button>
    </div>
    <p className="gallery-file-name">{state?.image.file_name}</p>
    <div className="annotation-toolbar">
      {(['draw', 'select', 'pan'] as const).map(tool => <button key={tool} className="ghost-button" aria-pressed={mode === tool} disabled={blocked} onClick={() => setMode(tool)}>{copy[tool]}</button>)}
      <button className="ghost-button" disabled={blocked || !ready} onClick={() => changeZoom(zoom * 1.25)}>{copy.zoomIn}</button>
      <button className="ghost-button" disabled={blocked || !ready} onClick={() => changeZoom(zoom / 1.25)}>{copy.zoomOut}</button>
      <button className="ghost-button" disabled={blocked || !ready} onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>{copy.fit}</button>
      <button className="ghost-button" disabled={blocked || !ready} onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); setMode('draw'); setSelected(null); }}>{copy.reset}</button>
      <span>{copy.zoom(number(zoom * 100))}</span>
    </div>
    <p className="annotation-save-state" aria-live="polite">{loading ? copy.loading : saving ? copy.saving : pending ? copy.saveFailed : !error ? copy.saved : ''}</p>
    {error && <div role="alert" className="field-error">{error} {pending && <button className="ghost-button" disabled={saving} onClick={() => void commit(pending)}>{copy.retry}</button>}<button className="ghost-button" disabled={saving} onClick={reloadSaved}>{copy.reload}</button></div>}
    <div className="annotation-workspace">
      <div ref={viewport} className={`annotation-viewport tool-${mode}`} tabIndex={0} role="application" aria-label={copy.canvas}
        onPointerDown={start} onPointerMove={move} onPointerUp={event => finish(event)} onPointerCancel={event => finish(event, true)}
        onContextMenu={event => event.preventDefault()}
        onWheel={event => { if (!blocked) { const bounds = event.currentTarget.getBoundingClientRect(); changeZoom(zoom * (event.deltaY < 0 ? 1.15 : 1 / 1.15), event.clientX - bounds.left, event.clientY - bounds.top); } }}>
        {state && <div className="annotation-image-layer" style={{ left, top, width: displayWidth, height: displayHeight }}>
          <img key={`${imageId}-${reload}`} src={state.image.original_url} alt={state.image.file_name} draggable={false} onLoad={() => setReady(true)} onError={() => { setReady(false); setError(copy.imageFailed); }} />
          <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true">{boxes.map(box => {
            const definition = classes.data?.classes.find(item => item.id === box.class_id);
            return <g key={box.id} data-box-id={box.id} className={selected === box.id ? 'selected-box' : ''}>
              <rect className="annotation-rect" x={box.center_x - box.width / 2} y={box.center_y - box.height / 2} width={box.width} height={box.height} fill="transparent" stroke={definition?.color ?? '#19a98f'} vectorEffect="non-scaling-stroke" />
              {selected === box.id && (['nw', 'ne', 'sw', 'se'] as const).map(handle => <rect key={handle} data-handle={handle} x={box.center_x + (handle.includes('w') ? -1 : 1) * box.width / 2 - 5 / displayWidth} y={box.center_y + (handle.includes('n') ? -1 : 1) * box.height / 2 - 5 / displayHeight} width={10 / displayWidth} height={10 / displayHeight} fill="white" stroke={definition?.color ?? '#19a98f'} vectorEffect="non-scaling-stroke" />)}
            </g>;
          })}</svg>
        </div>}
      </div>
      <aside className="annotation-sidebar">
        <label className="field"><span>{en.classes.active}</span><select aria-label={en.classes.active} value={active?.id ?? ''} disabled={blocked || classes.busy || classes.loading} onChange={event => void classes.select(event.target.value || null)}>
          <option value="">{copy.noClass}</option>{classes.data?.classes.map(item => <option key={item.id} value={item.id}>{number(item.class_index)} · {item.name}</option>)}
        </select></label>
        {classes.error && <p role="alert" className="field-error">{classes.error}</p>}
        {!active && <p>{copy.chooseClass}</p>}
        <h3>{copy.boxes}</h3>
        {!boxes.length && <p>{copy.noBoxes}</p>}
        <ul className="annotation-box-list">{boxes.map((box, index) => <li key={box.id}><button className="ghost-button" aria-pressed={selected === box.id} disabled={editingBlocked} onClick={() => { setSelected(box.id); setMode('select'); }}>{copy.box(number(index + 1), classes.data?.classes.find(item => item.id === box.class_id)?.name ?? copy.unknownClass)}</button></li>)}</ul>
        <p>{selectedBox ? copy.selected : copy.noSelection}</p>
        <button className="ghost-button" disabled={!selectedBox || !active || editingBlocked} onClick={() => { const box = { ...selectedBox!, class_id: active!.id }; setBoxes(previous => previous.map(item => item.id === box.id ? box : item)); void commit({ box, action: 'update', revision: state!.revision }); }}>{copy.assign}</button>
        <button className="danger-button" disabled={!selectedBox || editingBlocked} onClick={removeSelected}>{copy.delete}</button>
      </aside>
    </div>
    <p className="annotation-help">{copy.help}</p><p className="annotation-help">{copy.shortcuts}</p>
  </Dialog>;
}
