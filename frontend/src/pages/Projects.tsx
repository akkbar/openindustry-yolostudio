import { useCallback, useEffect, useRef, useState } from 'react';
import { CircleHelp, FolderOpen, Pencil, Plus, Trash2 } from 'lucide-react';
import {
  ApiError, createProject, deleteProject, getProject, listProjects, updateProject, type Project,
} from '../api';
import { APP_LOCALE, en } from '../locales/en';
import ImageImport from './ImageImport';

const copy = en.projects;

type Dialog =
  | { kind: 'create' }
  | { kind: 'rename'; project: Project }
  | { kind: 'delete'; project: Project };

const formatMoment = (value: string) => {
  const moment = new Date(value);
  return Number.isNaN(moment.getTime())
    ? value
    : new Intl.DateTimeFormat(APP_LOCALE, { dateStyle: 'medium', timeStyle: 'short' }).format(moment);
};

const describe = (error: unknown) =>
  error instanceof ApiError ? error.message : en.apiFailure;

export default function Projects() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Dialog | null>(null);
  const [selectedId, setSelectedId] = useState(() => window.location.hash.split('/')[1] ?? '');
  const [selected, setSelected] = useState<Project | null>(null);
  const [selectedError, setSelectedError] = useState<string | null>(null);

  useEffect(() => {
    const onHash = () => setSelectedId(window.location.hash.split('/')[1] ?? '');
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setSelected(null);
    setSelectedError(null);
    if (selectedId) void getProject(selectedId, controller.signal)
      .then(project => { if (!controller.signal.aborted) setSelected(project); })
      .catch(error => { if (!controller.signal.aborted) setSelectedError(describe(error)); });
    return () => controller.abort();
  }, [selectedId]);

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoadError(null);
    try {
      const result = await listProjects(signal);
      setProjects(result.projects);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return;
      setProjects(null);
      setLoadError(describe(error));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const total = projects?.length ?? 0;

  if (selectedId) return (
    <section className="project-workspace">
      <button className="ghost-button" onClick={() => { window.location.hash = 'Projects'; }}>{copy.backToProjects}</button>
      {selectedError ? <p className="field-error" role="alert">{selectedError}</p> : !selected ? <p>{copy.loading}</p> : <>
        <p className="eyebrow">{copy.overview}</p>
        <h2 className="project-name">{selected.name}</h2>
        {selected.description && <p className="project-description">{selected.description}</p>}
        <span className="project-task">{copy.taskType}</span>
        <dl className="project-meta">
          <div><dt>{copy.created}</dt><dd>{formatMoment(selected.created_at)}</dd></div>
          <div><dt>{copy.updated}</dt><dd>{formatMoment(selected.updated_at)}</dd></div>
        </dl>
        <dl><dt>{copy.storage}</dt><dd className="project-path">{selected.storage_path}</dd></dl>
        <p>{copy.workspaceDetail}</p>
        <button className="ghost-button" onClick={() => { window.location.hash = `Dataset/${selected.id}`; }}>{en.gallery.openGallery}</button>
        <button className="ghost-button" onClick={() => { window.location.hash = `Models/${selected.id}`; }}>{en.models.training.openTraining}</button>
        <ImageImport key={selected.id} projectId={selected.id} />
        <div className="workflow-grid">{(['Cameras', 'Runtime'] as const).map(page => <article className="workflow-card" key={page}>
          <h3>{en.navigation[page]}</h3><p>{en.pageDetails[page]}</p><span className="planned">{en.planned}</span>
        </article>)}</div>
      </>}
    </section>
  );

  return (
    <section className="projects-page">
      <div className="project-toolbar">
        <div>
          <p className="eyebrow">{en.navigation.Projects}</p>
          <p className="project-count">
            {projects === null ? copy.loading
              : total === 1 ? copy.countOne
              : copy.countMany(new Intl.NumberFormat(APP_LOCALE).format(total))}
          </p>
        </div>
        <button className="primary-button" onClick={() => setDialog({ kind: 'create' })}>
          <Plus size={17} />{copy.newProject}
        </button>
      </div>

      {loadError && (
        <div className="error-banner" role="alert">
          <CircleHelp size={20} />
          <span>{loadError}</span>
          <button onClick={() => void load()}>{copy.retry}</button>
        </div>
      )}


      {projects !== null && total === 0 && !loadError && (
        <div className="empty-state">
          <span className="empty-icon"><FolderOpen size={32} /></span>
          <h2>{copy.emptyTitle}</h2>
          <p>{copy.emptyDetail}</p>
          <button className="primary-button" onClick={() => setDialog({ kind: 'create' })}>
            <Plus size={17} />{copy.newProject}
          </button>
        </div>
      )}

      {total > 0 && (
        <ul className="project-grid">
          {projects?.map((project) => (
            <li className="project-card" key={project.id}>
              <div className="project-card-top">
                <h2>{project.name}</h2>
                <span className="project-task">{copy.taskType}</span>
              </div>
              {project.description && <p className="project-description">{project.description}</p>}
              <dl className="project-meta">
                <div><dt>{copy.created}</dt><dd>{formatMoment(project.created_at)}</dd></div>
                <div><dt>{copy.updated}</dt><dd>{formatMoment(project.updated_at)}</dd></div>
              </dl>
              <div className="project-actions">
                <button
                  className="ghost-button"
                  onClick={() => { window.location.hash = `Projects/${project.id}`; }}
                  aria-label={`${copy.open} ${project.name}`}
                >
                  <FolderOpen size={15} />{copy.open}
                </button>
                <button
                  className="ghost-button"
                  onClick={() => setDialog({ kind: 'rename', project })}
                  aria-label={`${copy.rename} ${project.name}`}
                >
                  <Pencil size={15} />{copy.rename}
                </button>
                <button
                  className="ghost-button danger"
                  onClick={() => setDialog({ kind: 'delete', project })}
                  aria-label={`${copy.remove} ${project.name}`}
                >
                  <Trash2 size={15} />{copy.remove}
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {dialog?.kind === 'delete' ? (
        <DeleteDialog
          project={dialog.project}
          onClose={() => setDialog(null)}
          onDeleted={async () => { setDialog(null); await load(); }}
        />
      ) : dialog ? (
        <ProjectDialog
          project={dialog.kind === 'rename' ? dialog.project : null}
          onClose={() => setDialog(null)}
          onSaved={async () => { setDialog(null); await load(); }}
        />
      ) : null}
    </section>
  );
}

/** Restores focus to the element that opened the dialog and closes on Escape. */
function useDialogShell(onClose: () => void, busy: boolean) {
  const container = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(null);
  const latest = useRef({ onClose, busy });
  latest.current = { onClose, busy };

  useEffect(() => {
    opener.current = document.activeElement;
    container.current?.querySelector<HTMLElement>('input, button')?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        if (!latest.current.busy) latest.current.onClose();
      }
      if (event.key === 'Tab') {
        const controls = Array.from(container.current?.querySelectorAll<HTMLElement>('input:not(:disabled), textarea:not(:disabled), button:not(:disabled)') ?? []);
        const first = controls[0];
        const last = controls.at(-1);
        if (!first) { event.preventDefault(); return; }
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      (opener.current as HTMLElement | null)?.focus?.();
    };
  }, []);

  return container;
}

function ProjectDialog(
  { project, onClose, onSaved }:
  { project: Project | null; onClose: () => void; onSaved: () => void | Promise<void> },
) {
  const [name, setName] = useState(project?.name ?? '');
  const [description, setDescription] = useState(project?.description ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const container = useDialogShell(onClose, busy);
  const heading = project ? copy.renameTitle : copy.createTitle;

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (project) await updateProject(project.id, { name, description });
      else await createProject({ name, description });
      await onSaved();
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (!busy && event.target === event.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="project-dialog-title" ref={container}>
        <h2 id="project-dialog-title">{heading}</h2>
        <p className="modal-detail">{project ? copy.renameDetail : copy.createDetail}</p>
        <label className="field">
          <span>{copy.nameLabel}</span>
          <input
            value={name}
            maxLength={80}
            placeholder={copy.namePlaceholder}
            onChange={(event) => setName(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter' && name.trim() && !busy) void submit(); }}
          />
        </label>
        <label className="field">
          <span>{copy.descriptionLabel}<i>{copy.descriptionOptional}</i></span>
          <textarea
            value={description}
            maxLength={500}
            rows={3}
            placeholder={copy.descriptionPlaceholder}
            onChange={(event) => setDescription(event.target.value)}
          />
        </label>
        {error && <p className="field-error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button className="ghost-button" onClick={onClose} disabled={busy}>{copy.cancel}</button>
          <button className="primary-button" onClick={() => void submit()} disabled={busy || !name.trim()}>
            {busy ? copy.saving : project ? copy.save : copy.create}
          </button>
        </div>
      </div>
    </div>
  );
}

function DeleteDialog(
  { project, onClose, onDeleted }:
  { project: Project; onClose: () => void; onDeleted: () => void | Promise<void> },
) {
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const container = useDialogShell(onClose, busy);

  const confirm = async () => {
    setBusy(true);
    setError(null);
    try {
      await deleteProject(project.id);
      await onDeleted();
    } catch (failure) {
      setError(describe(failure));
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onMouseDown={(event) => { if (!busy && event.target === event.currentTarget) onClose(); }}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby="delete-dialog-title" ref={container}>
        <h2 id="delete-dialog-title">{copy.deleteTitle}</h2>
        <p className="modal-detail">{copy.deleteDetail(project.name)}</p>
        <p className="project-path">{project.storage_path}</p>
        {error && <p className="field-error" role="alert">{error}</p>}
        <div className="modal-actions">
          <button className="ghost-button" onClick={onClose} disabled={busy}>{copy.cancel}</button>
          <button className="danger-button" onClick={() => void confirm()} disabled={busy}>
            {busy ? copy.deleting : copy.deleteConfirm}
          </button>
        </div>
      </div>
    </div>
  );
}
