import { useEffect, useState } from 'react';
import { Camera, CircleHelp, Play, RefreshCw, Square, Video } from 'lucide-react';
import {
  ApiError, type CameraDetection, type CameraSession, type Project, type UsbCamera,
  listProjects, listUsbCameras, readCameraFrame, startCameraSession, stopCameraSession,
} from '../api';
import { APP_LOCALE, en } from '../locales/en';

const describe = (failure: unknown, fallback: string) => failure instanceof ApiError ? failure.message : fallback;

export default function Cameras() {
  const copy = en.cameras;
  const [cameras, setCameras] = useState<UsbCamera[] | null>(null);
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [projectId, setProjectId] = useState(() => window.location.hash.split('/')[1] ?? '');
  const [error, setError] = useState<string | null>(null);
  const [scanning, setScanning] = useState(false);
  const [starting, setStarting] = useState<number | null>(null);
  const [session, setSession] = useState<CameraSession | null>(null);
  const [frameUrl, setFrameUrl] = useState<string | null>(null);
  const [detections, setDetections] = useState<CameraDetection[]>([]);
  const [confidence, setConfidence] = useState(0.5);

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

  useEffect(() => {
    if (!session) return;
    let disposed = false;
    let after = 0;
    let previousUrl: string | null = null;
    const controller = new AbortController();
    const poll = async () => {
      try {
        const frame = await readCameraFrame(session.project_id, session.id, after, controller.signal);
        if (disposed) { if (frame) URL.revokeObjectURL(frame.image_url); return; }
        if (frame) {
          after = frame.id;
          setDetections(frame.detections);
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
      void stopCameraSession(session.project_id, session.id).catch(() => {});
    };
  }, [session]);

  const start = async (camera: UsbCamera) => {
    if (!projectId) { setError(copy.chooseProject); return; }
    setStarting(camera.index); setError(null); setFrameUrl(null); setDetections([]);
    try { const next = await startCameraSession(projectId, camera.index); setSession(next); if (typeof next.recommended_confidence === 'number') setConfidence(next.recommended_confidence); }
    catch (failure) { setError(describe(failure, copy.previewFailed)); }
    finally { setStarting(null); }
  };

  const filtered = detections.filter(item => item.confidence >= confidence);
  const confidenceLabel = confidence.toLocaleString(APP_LOCALE, { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return <section className="cameras-page" aria-labelledby="usb-cameras-title">
    <header className="cameras-heading"><div><p className="eyebrow">{en.navigation.Cameras}</p><h2 id="usb-cameras-title">{copy.title}</h2><p>{copy.detail}</p></div><button className="primary-button" disabled={scanning} onClick={() => void scan()}><RefreshCw size={16} />{scanning ? copy.scanning : copy.scan}</button></header>
    <label className="camera-project"><span>{copy.project}</span><select value={projectId} disabled={!projects?.length || !!session} onChange={event => setProjectId(event.target.value)}><option value="">{copy.chooseProjectOption}</option>{projects?.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select><small>{copy.projectDetail}</small></label>
    {error && <p className="field-error" role="alert"><CircleHelp size={16} />{error}</p>}
    {session ? <CameraPreview session={session} imageUrl={frameUrl} detections={filtered} confidence={confidence} confidenceLabel={confidenceLabel} onConfidence={setConfidence} onStop={() => setSession(null)} /> : cameras === null && !error ? <p role="status">{copy.scanning}</p> : cameras?.length === 0 ? <div className="camera-empty"><Camera size={26} /><p>{copy.noCameras}</p></div> : <ul className="camera-list">{cameras?.map(camera => <li key={camera.id}><span className="camera-icon"><Camera size={21} /></span><div><strong>{camera.name}</strong><p>{copy.index(camera.index.toLocaleString(APP_LOCALE))}</p></div><span className="camera-available">{copy.available}</span><button disabled={!projectId || starting !== null} onClick={() => void start(camera)}><Play size={15} />{starting === camera.index ? copy.starting : copy.start}</button></li>)}</ul>}
  </section>;
}

function CameraPreview({ session, imageUrl, detections, confidence, confidenceLabel, onConfidence, onStop }: { session: CameraSession; imageUrl: string | null; detections: CameraDetection[]; confidence: number; confidenceLabel: string; onConfidence: (value: number) => void; onStop: () => void }) {
  const copy = en.cameras;
  return <section className="camera-preview" aria-labelledby="camera-preview-title">
    <header><div><p className="eyebrow">{copy.live}</p><h3 id="camera-preview-title">{copy.preview(session.camera_index.toLocaleString(APP_LOCALE))}</h3><p>{session.inference_status === 'ready' ? session.active_model_source === 'catalog' ? copy.inferenceCatalog : copy.inferenceReady : copy.noActiveModel}</p></div><button onClick={onStop}><Square size={15} />{copy.stop}</button></header>
    <div className="camera-frame" aria-label={copy.frame}>
      {imageUrl ? <><img src={imageUrl} alt={copy.frame} /><svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label={copy.overlay} role="img">{detections.map((item, index) => <g key={`${item.class_id}-${index}`}><rect x={item.x} y={item.y} width={item.width} height={item.height} /><text x={item.x} y={Math.max(0.04, item.y - 0.01)}>{`${item.class_name} ${(item.confidence * 100).toLocaleString(APP_LOCALE, { maximumFractionDigits: 0 })}%`}</text></g>)}</svg></> : <p role="status"><Video size={26} />{copy.loadingPreview}</p>}
    </div>
    <div className="confidence-control"><label htmlFor="confidence-threshold">{copy.confidence(confidenceLabel)}</label><input id="confidence-threshold" type="range" min="0" max="1" step="0.05" value={confidence} onChange={event => onConfidence(Number(event.target.value))} /></div>
    <section className="detection-results" aria-labelledby="detection-results-title"><h4 id="detection-results-title">{copy.detections}</h4>{detections.length ? <ul>{detections.map((item, index) => <li key={`${item.class_id}-${index}`}><strong>{item.class_name}</strong><span>{(item.confidence * 100).toLocaleString(APP_LOCALE, { maximumFractionDigits: 1 })}%</span></li>)}</ul> : <p>{copy.noDetections}</p>}</section>
  </section>;
}
