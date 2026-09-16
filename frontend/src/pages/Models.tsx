import { type FormEvent, useEffect, useState } from 'react';
import { AlertTriangle, Archive, Check, CircleHelp, HardDrive, Layers3, Play, RefreshCw, Search, ShieldCheck, X } from 'lucide-react';
import {
  ApiError, activateRegisteredModel, archiveRegisteredModel, cancelTrainingJob, createTrainingJob,
  createProjectFromCatalog, getTrainingJob, listModelCatalog, listProjects, listRegisteredModels, listTrainingJobs, selectCatalogModel, startTrainingJob,
  type BaseModel, type CatalogModel, type CatalogTask, type Project, type RegisteredModel, type TrainingJob,
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

  const jobIsActive = startedJob?.status === 'queued' || startedJob?.status === 'running';
  const controlsLocked = busy || !!pendingJob || jobIsActive;
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
        <button className="primary-button" disabled={!selectedProject || !loaded || !!loadError || busy || jobIsActive}>
          <Play size={16} />{busy ? copy.starting : pendingJob ? copy.retryStart : copy.start}
        </button>
      </div>
    </form>
    {projectId && <TrainingProgress projectId={projectId} job={startedJob} onUpdate={setStartedJob} />}
    {projectId && <ProjectModels projectId={projectId} refreshKey={startedJob?.status === 'completed' ? startedJob.id : ''} />}
  </section>;
}

const isActive = (job: TrainingJob) => job.status === 'queued' || job.status === 'running';
const metric = (metrics: Record<string, number> | null, keys: string[]) => {
  const value = keys.map(key => metrics?.[key]).find(value => typeof value === 'number');
  return typeof value === 'number' ? value.toLocaleString(APP_LOCALE, { maximumFractionDigits: 4 }) : '—';
};

function TrainingProgress({ projectId, job, onUpdate }: { projectId: string; job: TrainingJob | null; onUpdate: (job: TrainingJob | null) => void }) {
  const copy = en.models.progress;
  const [current, setCurrent] = useState<TrainingJob | null>(job);
  const [error, setError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setInterval> | undefined;
    const update = (next: TrainingJob | null) => {
      if (disposed) return;
      setCurrent(next); onUpdate(next);
      if (next && !isActive(next) && timer) clearInterval(timer);
    };
    const refresh = async () => {
      try {
        const target = job ?? (await listTrainingJobs(projectId)).jobs[0] ?? null;
        update(target ? await getTrainingJob(projectId, target.id) : null);
        if (!disposed) setError(null);
      } catch (failure) { if (!disposed) setError(describe(failure)); }
    };
    void refresh();
    timer = setInterval(() => { if (!current || isActive(current)) void refresh(); }, 1_000);
    return () => { disposed = true; if (timer) clearInterval(timer); };
  }, [projectId, job?.id]);

  const cancel = async () => {
    if (!current) return;
    setCancelling(true); setError(null);
    try {
      const next = await cancelTrainingJob(projectId, current.id);
      setCurrent(next); onUpdate(next);
    } catch (failure) { setError(describe(failure)); }
    finally { setCancelling(false); }
  };

  if (!current && !error) return <section className="training-progress" aria-live="polite"><p>{copy.noJob}</p></section>;
  const completedEpochs = Math.min(current?.epochs ?? 0, Math.round((current?.progress ?? 0) * (current?.epochs ?? 0)));
  const percent = Math.round((current?.progress ?? 0) * 100);
  return <section className="training-progress" aria-labelledby="training-progress-title" aria-busy={!!current && isActive(current)}>
    <header><div><h2 id="training-progress-title">{copy.title}</h2>{current && <p>{copy.epoch(completedEpochs.toLocaleString(APP_LOCALE), current.epochs.toLocaleString(APP_LOCALE))}</p>}</div>{current && <span className={`job-status ${current.status}`}>{copy[current.status]}</span>}</header>
    {current && <><progress value={current.progress} max={1}>{percent}%</progress><p className="training-percent">{percent.toLocaleString(APP_LOCALE)}%</p>
      <dl className="training-metrics"><div><dt>{copy.loss}</dt><dd>{metric(current.metrics, ['train/box_loss', 'box_loss'])}</dd></div><div><dt>{copy.precision}</dt><dd>{metric(current.metrics, ['metrics/precision(B)', 'precision'])}</dd></div><div><dt>{copy.recall}</dt><dd>{metric(current.metrics, ['metrics/recall(B)', 'recall'])}</dd></div><div><dt>{copy.map50}</dt><dd>{metric(current.metrics, ['metrics/mAP50(B)', 'mAP50'])}</dd></div></dl>
      {current.error && <p className="field-error" role="alert">{current.error}</p>}
      {isActive(current) && <button className="ghost-button danger" disabled={cancelling} onClick={() => void cancel()}><X size={15} />{cancelling ? copy.cancelling : copy.cancel}</button>}
      {isActive(current) && <p className="training-poll-note"><RefreshCw size={14} />{copy.updated}</p>}</>}
    {error && <p className="field-error" role="alert">{error}</p>}
  </section>;
}

function ProjectModels({ projectId, refreshKey }: { projectId: string; refreshKey: string }) {
  const copy = en.models.registry;
  const [models, setModels] = useState<RegisteredModel[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const load = async () => {
    setError(null);
    try { setModels((await listRegisteredModels(projectId)).models); }
    catch (failure) { setError(describe(failure)); }
  };
  useEffect(() => { void load(); }, [projectId, refreshKey]);
  const act = async (model: RegisteredModel, action: 'activate' | 'archive') => {
    setBusy(model.id); setError(null);
    try { await (action === 'activate' ? activateRegisteredModel(projectId, model.id) : archiveRegisteredModel(projectId, model.id)); await load(); }
    catch (failure) { setError(describe(failure) || copy.actionFailed); }
    finally { setBusy(null); }
  };
  return <section className="model-registry" aria-labelledby="model-registry-title">
    <header><div><h2 id="model-registry-title">{copy.title}</h2><p>{copy.detail}</p></div></header>
    {error && <p className="field-error" role="alert">{error}</p>}
    {models === null ? <p>{en.models.progress.loading}</p> : !models.length ? <p>{copy.empty}</p> : <ul>{models.map(model => <li key={model.id}>
      <div><strong>{model.name}</strong><span className={`model-status ${model.status}`}>{copy[model.status]}</span>{model.active && <span className="model-active">{copy.active}</span>}
        <p>{copy.version(model.version.toLocaleString(APP_LOCALE))} · {copy.map50}: {metric(model.metrics, ['metrics/mAP50(B)', 'mAP50'])}</p></div>
      <div className="model-actions">{model.status !== 'production' && model.status !== 'archived' && <button className="ghost-button" disabled={!!busy} onClick={() => void act(model, 'activate')}><Check size={15} />{copy.activate}</button>}{model.status !== 'archived' && <button className="ghost-button danger" disabled={!!busy} onClick={() => void act(model, 'archive')}><Archive size={15} />{copy.archive}</button>}</div>
    </li>)}</ul>}
  </section>;
}

const catalogTaskLabel = (task: CatalogTask) => {
  const copy = en.models.library;
  return task === 'detect' ? copy.taskDetect : task === 'pose' ? copy.taskPose : task === 'segment' ? copy.taskSegment : copy.taskClassify;
};

function ModelLibrary() {
  const copy = en.models.library;
  const [models, setModels] = useState<CatalogModel[] | null>(null);
  const [categories, setCategories] = useState<string[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(projectFromHash);
  const [category, setCategory] = useState('');
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ model: string; project: Project } | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    void listProjects(controller.signal).then(result => { if (!controller.signal.aborted) setProjects(result.projects); }).catch(failure => { if (!controller.signal.aborted) setError(describe(failure)); });
    return () => controller.abort();
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    setModels(null);
    void listModelCatalog(category, query, controller.signal).then(result => {
      if (!controller.signal.aborted) { setModels(result.models); setCategories(result.categories); }
    }).catch(failure => { if (!controller.signal.aborted) { setError(describe(failure)); setModels([]); } });
    return () => controller.abort();
  }, [category, query]);

  const useModel = async (model: CatalogModel) => {
    if (!projectId) { setError(copy.chooseProject); return; }
    setBusy(model.id); setError(null);
    try {
      await selectCatalogModel(projectId, model.id);
      const project = projects.find(item => item.id === projectId);
      if (project) setNotice({ model: model.name, project });
    } catch (failure) { setError(describe(failure) || copy.selectionFailed); }
    finally { setBusy(null); }
  };
  const createFromModel = async (model: CatalogModel) => {
    setBusy(`create-${model.id}`); setError(null);
    try {
      const project = await createProjectFromCatalog(model.id, { name: copy.newProject(model.name), description: copy.newDescription(model.name) });
      setProjects(current => [...current, project].sort((left, right) => left.name.localeCompare(right.name, APP_LOCALE)));
      setProjectId(project.id); setNotice({ model: model.name, project });
    } catch (failure) { setError(describe(failure) || copy.selectionFailed); }
    finally { setBusy(null); }
  };
  const runnable = (model: CatalogModel) => model.status === 'BUILT_IN' || model.status === 'INSTALLED';

  return <section className="model-library" aria-labelledby="model-library-title">
    <header><div><p className="eyebrow">{copy.eyebrow}</p><h2 id="model-library-title">{copy.title}</h2><p>{copy.detail}</p></div><Layers3 size={28} aria-hidden="true" /></header>
    <div className="catalog-controls"><label className="field"><span>{copy.search}</span><div className="catalog-search"><Search size={16} /><input value={query} placeholder={copy.search} onChange={event => setQuery(event.target.value)} /></div></label><label className="field"><span>{copy.category}</span><select value={category} onChange={event => setCategory(event.target.value)}><option value="">{copy.allCategories}</option>{categories.map(item => <option key={item} value={item}>{item}</option>)}</select></label><label className="field"><span>{copy.project}</span><select value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">{copy.chooseProject}</option>{projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}</select></label></div>
    {error && <p className="field-error" role="alert">{error}</p>}
    {notice && <div className="catalog-notice" role="status"><Check size={17} /><span>{copy.selected(notice.model, notice.project.name)}</span><button className="ghost-button" onClick={() => { window.location.hash = `Cameras/${notice.project.id}`; }}><Play size={15} />{copy.openCameras}</button></div>}
    {models === null ? <p>{copy.loading}</p> : !models.length ? <p>{copy.empty}</p> : <ul className="catalog-grid">{models.map(model => <li key={model.id} className="catalog-card">
      <div className="catalog-card-heading"><div><span className="catalog-category">{model.category}</span><h3>{model.name}</h3></div><span className={`catalog-status ${model.status.toLowerCase()}`}>{model.status === 'BUILT_IN' ? copy.ready : model.status === 'AVAILABLE' ? copy.available : model.status === 'INSTALLED' ? copy.installed : model.status === 'DOWNLOADING' ? copy.downloading : model.status === 'UPDATE_AVAILABLE' ? copy.update : copy.error}</span></div>
      <p>{model.description}</p><dl><div><dt>{copy.task}</dt><dd>{catalogTaskLabel(model.task)}</dd></div><div><dt>{copy.source}</dt><dd>{model.source_type === 'builtin' ? copy.builtin : copy.downloadable}</dd></div><div><dt>{copy.version}</dt><dd>{model.model_version}</dd></div></dl>
      <div className="catalog-classes"><strong>{copy.classes}</strong><span>{model.classes.slice(0, 12).join(', ')}{model.classes.length > 12 ? ` +${model.classes.length - 12}` : ''}</span></div>
      {model.fine_tuning_recommended && <p className="catalog-fine"><AlertTriangle size={15} />{copy.fineTuning}</p>}
      {model.redistribution_allowed === false && <p className="catalog-warning"><AlertTriangle size={15} />{copy.sourceWarning}</p>}
      <div className="catalog-actions">{runnable(model) ? <><button className="ghost-button" disabled={!!busy} onClick={() => void useModel(model)}><Play size={15} />{busy === model.id ? copy.using : copy.use}</button><button className="primary-button" disabled={!!busy} onClick={() => void createFromModel(model)}><Layers3 size={15} />{busy === `create-${model.id}` ? copy.creating : copy.create}</button></> : <span>{copy.available}</span>}</div>
    </li>)}</ul>}
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
    <ModelLibrary />
    <TrainingForm baseModel={baseModel} />
  </section>;
}
