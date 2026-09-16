import { type MouseEvent, useEffect, useState } from 'react';
import { Camera, CircleHelp, Crosshair, MapPinned, Play, Plus, RefreshCw, Square, Trash2, Video } from 'lucide-react';
import {
  ApiError, type CameraDetection, type CameraSession, type CountingConfiguration, type CountingDirection, type NormalizedPoint, type Project, type RtspCamera, type UsbCamera, type VisionEvent,
  createCountingLine, createRtspCamera, deleteCountingLine, deleteProjectRoi, deleteRtspCamera, getCountingConfiguration, listEvents, listProjects, listRtspCameras, listUsbCameras, readCameraFrame,
  reloadCameraCounting, saveProjectRoi, startCameraSession, startRtspCameraSession, stopCameraSession, updateCountingLine,
} from '../api';
import { APP_LOCALE, en } from '../locales/en';

const describe = (failure: unknown, fallback: string) => failure instanceof ApiError ? failure.message : fallback;

type DrawMode = 'line' | 'roi' | null;

export default function Cameras() {
  const copy = en.cameras;
  const [cameras, setCameras] = useState<UsbCamera[] | null>(null);
  const [rtspCameras, setRtspCameras] = useState<RtspCamera[]>([]);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState(() => window.location.hash.split('/')[1] ?? '');
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [starting, setStarting] = useState<number | null>(null);
  const [session, setSession] = useState<CameraSession | null>(null);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [detections, setDetections] = useState<CameraDetection[]>([]);
  const [confidence, setConfidence] = useState(0.5);
  const [rtspDraft, setRtspDraft] = useState({ name: '', url: '', username: '', password: '' });
  const [savingRtsp, setSavingRtsp] = useState(false);

  const scan = async () => {
    setScanning(true); setError(null);
    try { setCameras((await listUsbCameras()).cameras); }
    catch (failure) { setError(describe(failure, copy.scanFailed)); setCameras(null); }
    finally { setScanning(false); }
  };

  useEffect(() => { void scan(); }, []);
  useEffect(() => {
    let active = true;
    void listProjects().then(result => {
      if (!active) return;
      setProjects(result.projects);
      setProjectId(current => current || result.projects[0]?.id || '');
    }).catch(failure => { if (active) setError(describe(failure, copy.projectsFailed)); });
    return () => { active = false; };
  }, []);
  const loadRtsp = async (id = projectId) => {
    if (!id) { setRtspCameras([]); return; }
    try { setRtspCameras((await listRtspCameras(id)).cameras); }
    catch (failure) { setError(describe(failure, copy.rtspFailed)); }
  };
  useEffect(() => { void loadRtsp(); }, [projectId]);

  useEffect(() => {
    if (!session) return;
    let disposed = false;
    let after = 0;
    let previousUrl: string | null = null;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const frame = await readCameraFrame(session.project_id, session.id, after, session.source_type, controller.signal);
        if (disposed) { if (frame) URL.revokeObjectURL(frame.image_url); return; }
        if (frame) {
          after = frame.id;
          setDetections(frame.detections);
          setSession(current => current?.id === session.id ? { ...current, counters: frame.counters, roi_active: frame.roi_active } : current);
          setFrameUrl(current => { if (current) URL.revokeObjectURL(current); previousUrl = frame.image_url; return frame.image_url; });
        }
        window.setTimeout(() => { if (!disposed) void poll(); }, 25);
      } catch (failure) {
        if (!disposed && !(failure instanceof DOMException && failure.name === 'AbortError')) setError(describe(failure, copy.previewFailed));
      }
    };
    void poll();
    return () => {
      disposed = true;
      controller.abort();
      if (previousUrl) URL.revokeObjectURL(previousUrl);
      void stopCameraSession(session.project_id, session.id, session.source_type).catch(() => {});
    };
  }, [session?.id]);

  const start = async (camera: UsbCamera) => {
    if (!projectId) { setError(copy.chooseProject); return; }
    setStarting(camera.index); setError(null); setFrameUrl(null); setDetections([]);
    try { const next = await startCameraSession(projectId, camera); setSession(next); if (typeof next.recommended_confidence === 'number') setConfidence(next.recommended_confidence); }
    catch (failure) { setError(describe(failure, copy.previewFailed)); }
    finally { setStarting(null); }
  };
  const startRtsp = async (camera: RtspCamera) => {
    if (!projectId) { setError(copy.chooseProject); return; }
    setStarting(-1); setError(null); setFrameUrl(null); setDetections([]);
    try { const next = await startRtspCameraSession(projectId, camera.id); setSession(next); if (typeof next.recommended_confidence === 'number') setConfidence(next.recommended_confidence); }
    catch (failure) { setError(describe(failure, copy.previewFailed)); }
    finally { setStarting(null); }
  };
  const saveRtsp = async () => {
    if (!projectId) { setError(copy.chooseProject); return; }
    setSavingRtsp(true); setError(null);
    try {
      await createRtspCamera(projectId, { name: rtspDraft.name, url: rtspDraft.url, username: rtspDraft.username || null, password: rtspDraft.password || undefined });
      setRtspDraft({ name: '', url: '', username: '', password: '' });
      await loadRtsp(projectId);
    } catch (failure) { setError(describe(failure, copy.rtspFailed)); }
    finally { setSavingRtsp(false); }
  };
  const removeRtsp = async (camera: RtspCamera) => {
    if (!projectId) return;
    try { await deleteRtspCamera(projectId, camera.id); await loadRtsp(projectId); }
    catch (failure) { setError(describe(failure, copy.rtspFailed)); }
  };

  const filtered = detections.filter(item => item.confidence >= confidence);
  const confidenceLabel = confidence.toLocaleString(APP_LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return <section className="cameras-page" aria-labelledby="usb-cameras-title">
    <header className="cameras-heading"><div><p className="eyebrow">{en.navigation.Cameras}</p><h2 id="usb-cameras-title">{copy.title}</h2><p>{copy.detail}</p></div><button className="primary-button" disabled={scanning} onClick={() => void scan()}><RefreshCw size={16} />{scanning ? copy.scanning : copy.scan}</button></header>
    <label className="camera-project"><span>{copy.project}</span><select value={projectId} disabled={!projects?.length || !!session} onChange={event => setProjectId(event.target.value)}><option value="">{copy.chooseProjectOption}</option>{projects?.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><small>{copy.projectDetail}</small></label>
    {error && <p className="field-error" role="alert"><CircleHelp size={16} />{error}</p>}
    {session ? <CameraPreview session={session} imageUrl={frameUrl} detections={filtered} confidence={confidence} confidenceLabel={confidenceLabel} onConfidence={setConfidence} onStop={() => setSession(null)} onSessionChange={setSession} onFailure={message => setError(message)} /> : <>
      {projectId && <section className="rtsp-cameras" aria-labelledby="rtsp-cameras-title"><header><div><p className="eyebrow">{copy.rtspEyebrow}</p><h3 id="rtsp-cameras-title">{copy.rtspTitle}</h3><p>{copy.rtspDetail}</p></div></header><form onSubmit={event => { event.preventDefault(); void saveRtsp(); }}><label><span>{copy.rtspName}</span><input required value={rtspDraft.name} onChange={event => setRtspDraft(current => ({ ...current, name: event.target.value }))} /></label><label><span>{copy.rtspUrl}</span><input required type="url" placeholder="rtsp://camera.local/stream" value={rtspDraft.url} onChange={event => setRtspDraft(current => ({ ...current, url: event.target.value }))} /></label><label><span>{copy.rtspUsername}</span><input value={rtspDraft.username} onChange={event => setRtspDraft(current => ({ ...current, username: event.target.value }))} /></label><label><span>{copy.rtspPassword}</span><input type="password" value={rtspDraft.password} onChange={event => setRtspDraft(current => ({ ...current, password: event.target.value }))} /></label><button className="primary-button" disabled={savingRtsp}><Plus size={15} />{savingRtsp ? copy.savingRtsp : copy.addRtsp}</button></form>{rtspCameras.length ? <ul className="camera-list">{rtspCameras.map(camera => <li key={camera.id}><span className="camera-icon"><Video size={21} /></span><div><strong>{camera.name}</strong><p>{camera.url}</p></div><span className="camera-available">{copy.rtspAvailable}</span><button disabled={starting !== null} onClick={() => void startRtsp(camera)}><Play size={15} />{starting === -1 ? copy.starting : copy.start}</button><button className="icon-button" aria-label={copy.removeRtsp(camera.name)} disabled={starting !== null} onClick={() => void removeRtsp(camera)}><Trash2 size={15} /></button></li>)}</ul> : <p className="rtsp-empty">{copy.noRtsp}</p>}</section>}
      {cameras === null && !error ? <p role="status">{copy.scanning}</p> : cameras?.length === 0 ? <div className="camera-empty"><Camera size={26} /><p>{copy.noCameras}</p></div> : <ul className="camera-list">{cameras?.map(camera => <li key={camera.id}><span className="camera-icon"><Camera size={21} /></span><div><strong>{camera.name}</strong><p>{copy.usbDetail}</p></div><span className="camera-available">{copy.available}</span><button disabled={!projectId || starting !== null} onClick={() => void start(camera)}><Play size={15} />{starting === camera.index ? copy.starting : copy.start}</button></li>)}</ul>}
    </>}
  </section>;
}

function CameraPreview({ session, imageUrl, detections, confidence, confidenceLabel, onConfidence, onStop, onSessionChange, onFailure }: { session: CameraSession; imageUrl: string | null; detections: CameraDetection[]; confidence: number; confidenceLabel: string; onConfidence: (value: number) => void; onStop: () => void; onSessionChange: (next: CameraSession) => void; onFailure: (message: string) => void }) {
  const copy = en.cameras;
  const [configuration, setConfiguration] = useState<CountingConfiguration | null>(null);
  const [drawMode, setDrawMode] = useState<DrawMode>(null);
  const [draft, setDraft] = useState<NormalizedPoint[]>([]);
  const [saving, setSaving] = useState(false);
  const [events, setEvents] = useState<VisionEvent[]>([]);

  const load = async () => {
    try { setConfiguration(await getCountingConfiguration(session.project_id)); }
    catch (failure) { onFailure(describe(failure, copy.countingFailed)); }
  };
  useEffect(() => { void load(); }, [session.id]);
  useEffect(() => { let active = true; const loadEvents = () => { void listEvents(session.project_id).then(result => { if (active) setEvents(result.events); }).catch(() => {}); }; loadEvents(); const timer = window.setInterval(loadEvents, 1000); return () => { active = false; window.clearInterval(timer); }; }, [session.id, session.project_id]);
  const apply = async () => {
    const next = await reloadCameraCounting(session.project_id, session.id, session.source_type);
    onSessionChange(next);
    await load();
  };
  const pointFromEvent = (event: MouseEvent<SVGSVGElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: Math.max(0, Math.min(1, (event.clientX - bounds.left) / bounds.width)), y: Math.max(0, Math.min(1, (event.clientY - bounds.top) / bounds.height)) };
  };
  const addPoint = (event: MouseEvent<SVGSVGElement>) => {
    if (!drawMode || saving) return;
    const next = [...draft, pointFromEvent(event)];
    if (drawMode === 'line' && next.length === 2) {
      setSaving(true);
      void createCountingLine(session.project_id, { name: copy.lineName((configuration?.lines.length ?? 0) + 1), start: next[0], end: next[1], direction: 'both', enabled: true }).then(apply).catch(failure => onFailure(describe(failure, copy.countingFailed))).finally(() => { setSaving(false); setDraft([]); setDrawMode(null); });
      return;
    }
    setDraft(next);
  };
  const saveRoi = () => {
    if (draft.length < 3) { onFailure(copy.roiMinimum); return; }
    setSaving(true);
    void saveProjectRoi(session.project_id, { points: draft, enabled: true }).then(apply).catch(failure => onFailure(describe(failure, copy.countingFailed))).finally(() => { setSaving(false); setDraft([]); setDrawMode(null); });
  };
  const removeLine = (lineId: string) => { setSaving(true); void deleteCountingLine(session.project_id, lineId).then(apply).catch(failure => onFailure(describe(failure, copy.countingFailed))).finally(() => setSaving(false)); };
  const changeDirection = (line: NonNullable<CountingConfiguration>['lines'][number], direction: CountingDirection) => { setSaving(true); void updateCountingLine(session.project_id, line.id, { name: line.name, start: line.start, end: line.end, direction, enabled: line.enabled }).then(apply).catch(failure => onFailure(describe(failure, copy.countingFailed))).finally(() => setSaving(false)); };
  const clearRoi = () => { setSaving(true); void deleteProjectRoi(session.project_id).then(apply).catch(failure => onFailure(describe(failure, copy.countingFailed))).finally(() => setSaving(false)); };
  const lines = configuration?.lines ?? [];
  const roiPoints = configuration?.roi?.points ?? [];

  return <section className="camera-preview" aria-labelledby="camera-preview-title">
    <header><div><p className="eyebrow">{copy.live}</p><h3 id="camera-preview-title">{session.camera_name ? copy.namedPreview(session.camera_name) : copy.preview((session.camera_index ?? 0).toLocaleString(APP_LOCALE))}</h3><p>{session.inference_status === 'ready' ? session.active_model_source === 'catalog' ? copy.inferenceCatalog : copy.inferenceReady : copy.noActiveModel}{session.source_type === 'rtsp' && session.reconnect_count > 0 ? ` ${copy.reconnects(session.reconnect_count.toLocaleString(APP_LOCALE))}` : ''}</p>{session.video_status === 'black_frames' && <p className="camera-video-warning" role="status">{copy.blackFrames}</p>}</div><button onClick={onStop}><Square size={15} />{copy.stop}</button></header>
    <div className={`camera-frame ${drawMode ? 'drawing' : ''}`} aria-label={copy.frame}>
      {imageUrl ? <><img src={imageUrl} alt={copy.frame} /><svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label={copy.overlay} role="img" onClick={addPoint}>{roiPoints.length >= 3 && <polygon className="roi-shape" points={roiPoints.map(point => `${point.x},${point.y}`).join(' ')} />}{drawMode === 'roi' && draft.length >= 2 && <polyline className="roi-draft" points={draft.map(point => `${point.x},${point.y}`).join(' ')} />}{drawMode === 'roi' && draft.map((point, index) => <circle className="roi-point" key={index} cx={point.x} cy={point.y} r="0.012" />)}{lines.map(line => <line className="counting-line" key={line.id} x1={line.start.x} y1={line.start.y} x2={line.end.x} y2={line.end.y} />)}{drawMode === 'line' && draft[0] && <circle className="line-point" cx={draft[0].x} cy={draft[0].y} r="0.014" />}{detections.map((item, index) => <g key={`${item.track_id ?? item.class_id}-${index}`}><rect x={item.x} y={item.y} width={item.width} height={item.height} /><text x={item.x} y={Math.max(0.04, item.y - 0.01)}>{`${item.class_name} ${(item.confidence * 100).toLocaleString(APP_LOCALE, { maximumFractionDigits: 0 })}${item.track_id ? ` #${item.track_id}` : ''}`}</text></g>)}</svg></> : <p role="status"><Video size={26} />{copy.loadingPreview}</p>}
    </div>
    <div className="confidence-control"><label htmlFor="confidence-threshold">{copy.confidence(confidenceLabel)}</label><input id="confidence-threshold" type="range" min="0" max="1" step="0.05" value={confidence} onChange={event => onConfidence(Number(event.target.value))} /></div>
    <section className="counting-controls" aria-labelledby="counting-title"><header><div><h4 id="counting-title">{copy.countingTitle}</h4><p>{copy.countingDetail}</p></div><span>{session.roi_active ? copy.roiActive : copy.roiInactive}</span></header><div className="counting-actions"><button className="ghost-button" disabled={saving || !imageUrl} onClick={() => { setDrawMode('line'); setDraft([]); }}><Crosshair size={15} />{copy.drawLine}</button><button className="ghost-button" disabled={saving || !imageUrl} onClick={() => { setDrawMode('roi'); setDraft([]); }}><MapPinned size={15} />{copy.drawRoi}</button>{drawMode === 'roi' && <button className="primary-button" disabled={saving || draft.length < 3} onClick={saveRoi}>{copy.saveRoi}</button>}{drawMode && <button className="ghost-button" disabled={saving} onClick={() => { setDrawMode(null); setDraft([]); }}>{copy.cancelDrawing}</button>}</div>{drawMode && <p className="drawing-hint">{drawMode === 'line' ? copy.lineHint : copy.roiHint(draft.length.toLocaleString(APP_LOCALE))}</p>}
      {!!lines.length && <ul className="counting-lines">{lines.map(line => <li key={line.id}><strong>{line.name}</strong><label><span>{copy.direction}</span><select value={line.direction} disabled={saving} onChange={event => changeDirection(line, event.target.value as CountingDirection)}><option value="both">{copy.bothDirections}</option><option value="a_to_b">{copy.aToB}</option><option value="b_to_a">{copy.bToA}</option></select></label><button className="icon-button" aria-label={copy.removeLine(line.name)} disabled={saving} onClick={() => removeLine(line.id)}><Trash2 size={15} /></button></li>)}</ul>}{configuration?.roi && <button className="ghost-button danger" disabled={saving} onClick={clearRoi}><Trash2 size={15} />{copy.clearRoi}</button>}</section>
    <section className="counter-results" aria-labelledby="counter-results-title"><h4 id="counter-results-title">{copy.counters}</h4>{(session.counters ?? []).length ? <ul>{(session.counters ?? []).map(counter => <li key={counter.line_id}><strong>{counter.line_name}</strong><b>{counter.count.toLocaleString(APP_LOCALE)}</b><span>{copy.directionTotals(counter.a_to_b.toLocaleString(APP_LOCALE), counter.b_to_a.toLocaleString(APP_LOCALE))}</span></li>)}</ul> : <p>{copy.noCounters}</p>}</section>
    <section className="event-results" aria-labelledby="event-results-title"><h4 id="event-results-title">{copy.events}</h4>{events.length ? <ul>{events.map(event => <li key={event.id}>{event.snapshot_url && <img src={event.snapshot_url} alt={copy.eventSnapshot(event.id.toLocaleString(APP_LOCALE))} />}<div><strong>{event.class_name ?? copy.unknownClass}{event.track_id ? ` #${event.track_id}` : ''}</strong><span>{copy.eventCount((event.count ?? 0).toLocaleString(APP_LOCALE))}</span><small>{new Date(event.occurred_at).toLocaleString(APP_LOCALE)}</small></div></li>)}</ul> : <p>{copy.noEvents}</p>}</section>
    <section className="detection-results" aria-labelledby="detection-results-title"><h4 id="detection-results-title">{copy.detections}</h4>{detections.length ? <ul>{detections.map((item, index) => <li key={`${item.track_id ?? item.class_id}-${index}`}><strong>{item.class_name}{item.track_id ? ` #${item.track_id}` : ''}</strong><span>{(item.confidence * 100).toLocaleString(APP_LOCALE, { maximumFractionDigits: 1 })}%</span></li>)}</ul> : <p>{copy.noDetections}</p>}</section>
  </section>;
}
