import { type FormEvent, useEffect, useState } from 'react';
import { Check, CircleHelp, HardDrive, Play, ShieldCheck } from 'lucide-react';
import {
  ApiError, createTrainingJob, listProjects, startTrainingJob,
  type BaseModel, type Project, type TrainingJob,
} from '../api';
import { APP_LOCALE, en } from '../locales/en';

interface ModelsProps {
  baseModel: BaseModel | null;
}

const describe = (failure: unknown) =>
  failure instanceof ApiError ? failure.message : en.apiFailure;

const projectFromHash = () => window.location.hash.slice(1).split('/')[1] ?? '';

function TrainingForm({ baseModel }: { baseModel: BaseModel }) {
  const copy = en.models.training;
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(projectFromHash);
  const [projectReload, setProjectReload] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [epochs, setEpochs] = useState('50');
  const [imgsz, setImageSize] = useState('640');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pendingJob, setPendingJob] = useState<TrainingJob | null>(null);
  const [startedJob, setStartedJob] = useState<TrainingJob | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(null);
    setLoaded(false);
    void listProjects(controller.signal).then(result => {
      if (!controller.signal.aborted) { setProjects(result.projects); setLoaded(true); }
    }).catch(failure => {
      if (!controller.signal.aborted) setLoadError(describe(failure));
    });
    return () => controller.abort();
  }, [projectReload]);

  useEffect(() => {
    const onHashChange = () => setProjectId(projectFromHash());
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, []);

  useEffect(() => {
    setError(null);
    setPendingJob(null);
    setStartedJob(null);
  }, [projectId]);

  const resetLaunch = () => {
    setError(null);
    setPendingJob(null);
    setStartedJob(null);
  };

  const chooseProject = (value: string) => {
    if (value === projectId) return;
    window.location.hash = value ? `Models/${value}` : 'Models';
  };

  const selectedProject = projects.some(project => project.id === projectId);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!projectId || !selectedProject) { setError(copy.invalidProject); return; }
    const parsedEpochs = Number(epochs);
    if (!Number.isSafeInteger(parsedEpochs) || parsedEpochs < 1 || parsedEpochs > 10_000) {
      setError(copy.invalidEpochs); return;
    }
    const parsedImageSize = Number(imgsz);
    if (!Number.isSafeInteger(parsedImageSize) || parsedImageSize < 32 || parsedImageSize > 4_096) {
      setError(copy.invalidImageSize); return;
    }

    setBusy(true);
    let job = pendingJob;
    try {
      if (!job) {
        job = await createTrainingJob(projectId, {
          model: 'yolo11n', epochs: parsedEpochs, imgsz: parsedImageSize,
        });
      }
      const started = await startTrainingJob(projectId, job.id);
      setPendingJob(null);
      setStartedJob(started);
    } catch (failure) {
      if (job) setPendingJob(job);
      setError(describe(failure));
    } finally {
      setBusy(false);
    }
  };

  const controlsLocked = busy || !!pendingJob || !!startedJob;
  return <section className="training-panel" aria-labelledby="training-title">
    <header className="training-heading">
      <div><p className="eyebrow">{copy.title}</p><h2 id="training-title">{copy.title}</h2><p>{copy.detail}</p></div>
      <span className="training-worker"><Play size={16} />{copy.deviceAuto}</span>
    </header>
    <form className="training-form" aria-busy={busy} noValidate onSubmit={event => void submit(event)}>
      <label className="field training-wide-field"><span>{copy.project}</span>
        <select value={projectId} disabled={controlsLocked || !loaded || !!loadError} onChange={event => chooseProject(event.target.value)}>
          <option value="">{copy.chooseProject}</option>
          {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
        </select>
      </label>
      <label className="field"><span>{copy.baseModel}</span><input value={baseModel.display_name} readOnly /></label>
      <label className="field"><span>{copy.device}</span><input value={copy.deviceAuto} readOnly /></label>
      <label className="field"><span>{copy.epochs}</span>
        <input type="number" min="1" max="10000" step="1" inputMode="numeric" value={epochs} disabled={controlsLocked} onChange={event => { resetLaunch(); setEpochs(event.target.value); }} />
      </label>
      <label className="field"><span>{copy.imageSize}</span>
        <input type="number" min="32" max="4096" step="1" inputMode="numeric" value={imgsz} disabled={controlsLocked} onChange={event => { resetLaunch(); setImageSize(event.target.value); }} />
      </label>
      <div className="training-wide-field training-notes"><p>{copy.modelDetail}</p><p>{copy.deviceDetail}</p><p>{copy.datasetNote}</p></div>
      {loadError && <div className="error-banner training-wide-field" role="alert"><CircleHelp size={20} /><span>{copy.projectLoadFailed}</span><button type="button" onClick={() => { setProjectReload(value => value + 1); }}>{copy.retryProjects}</button></div>}
      {loaded && !projects.length && <p className="training-empty training-wide-field">{copy.noProjects} <button type="button" className="ghost-button" onClick={() => { window.location.hash = 'Projects'; }}>{copy.goToProjects}</button></p>}
      {error && <p className="field-error training-wide-field" role="alert">{error}</p>}
      {pendingJob && <p className="training-pending training-wide-field">{copy.queuedDetail}</p>}
      {startedJob && <div className="training-result training-wide-field" role="status"><Check size={20} /><div><strong>{copy.started}</strong><p>{copy.startedDetail}</p><span>{copy.jobId}: <code>{startedJob.id}</code></span></div></div>}
      <div className="training-actions training-wide-field">
        <button className="primary-button" disabled={!selectedProject || !loaded || !!loadError || busy || !!startedJob}>
          <Play size={16} />{busy ? copy.starting : pendingJob ? copy.retryStart : copy.start}
        </button>
      </div>
    </form>
  </section>;
}

export default function Models({ baseModel }: ModelsProps) {
  const copy = en.models;
  if (!baseModel) {
    return <section className="models-page empty-state"><span className="empty-icon"><HardDrive size={32} /></span><h2>{copy.unavailableTitle}</h2><p>{copy.unavailableDetail}</p></section>;
  }

  const size = (baseModel.byte_size / (1024 * 1024)).toLocaleString(APP_LOCALE, { maximumFractionDigits: 1 });
  return <section className="models-page" aria-label={copy.title}>
    <article className="base-model-card">
      <div className="base-model-header"><div><p className="eyebrow">{copy.bundled}</p><h2>{baseModel.display_name}</h2><p>{copy.detail}</p></div><span className="model-ready"><Check size={16} />{copy.ready}</span></div>
      <dl className="base-model-details">
        <div><dt>{copy.task}</dt><dd>{copy.objectDetection}</dd></div>
        <div><dt>{copy.distribution}</dt><dd>{copy.bundled}</dd></div>
        <div><dt>{copy.size}</dt><dd>{copy.sizeValue(size)}</dd></div>
        <div><dt>{copy.integrity}</dt><dd>{baseModel.load_verified ? copy.verified : copy.notVerified}</dd></div>
      </dl>
      <div className="base-model-note"><ShieldCheck size={18} /><p>{copy.offline}</p></div>
      <dl className="base-model-file">
        <div><dt>{copy.file}</dt><dd>{baseModel.file_name}</dd></div>
        <div><dt>{copy.location}</dt><dd>{baseModel.path}</dd></div>
        <div><dt>{copy.checksum}</dt><dd>{baseModel.sha256}</dd></div>
        <div><dt>{copy.license}</dt><dd>{baseModel.license}</dd></div>
      </dl>
      <p className="base-model-boundary">{copy.boundary}</p>
    </article>
    <TrainingForm baseModel={baseModel} />
  </section>;
}
