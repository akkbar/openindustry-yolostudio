import { useEffect, useState } from 'react';
import { ApiError, listProjects, type Project } from '../api';
import { en } from '../locales/en';
import ImageImport from './ImageImport';
import Gallery from './Gallery';
import ClassManager from './ClassManager';
import DatasetExport from './DatasetExport';
import { ProjectClassesProvider } from '../state/ProjectClasses';

function DatasetWorkspace({ projectId }: { projectId: string }) {
  const [imports, setImports] = useState(0);
  const [deletions, setDeletions] = useState(0);
  return <ProjectClassesProvider projectId={projectId}><div className="dataset-workspace">
    <ClassManager />
    <div className="dataset-images">
    <Gallery projectId={projectId} refreshToken={imports} onDeleted={() => setDeletions(value => value + 1)} />
    <ImageImport projectId={projectId} refreshToken={deletions} onImported={() => setImports(value => value + 1)} />
    <DatasetExport projectId={projectId} />
    </div>
  </div></ProjectClassesProvider>;
}

export default function Dataset() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState(() => window.location.hash.split('/')[1] ?? '');
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    void listProjects(controller.signal).then(result => {
      if (!controller.signal.aborted) { setProjects(result.projects); setLoaded(true); }
    }).catch(failure => { if (!controller.signal.aborted) setError(failure instanceof ApiError ? failure.message : en.connectionFailure); });
    const onHash = () => setProjectId(window.location.hash.split('/')[1] ?? '');
    window.addEventListener('hashchange', onHash);
    return () => { controller.abort(); window.removeEventListener('hashchange', onHash); };
  }, []);
  return <section>
    <div className="dataset-picker"><label className="field"><span>{en.imageImport.projectLabel}</span>
      <select value={projectId} onChange={event => { window.location.hash = event.target.value ? `Dataset/${event.target.value}` : 'Dataset'; }}>
        <option value="">{en.imageImport.chooseProject}</option>
        {projects.map(project => <option key={project.id} value={project.id}>{project.name}</option>)}
      </select></label><p>{en.imageImport.selectDetail}</p></div>
    {error && <p className="field-error" role="alert">{error}</p>}
    {loaded && !projects.length && <p>{en.imageImport.noProjects} <button className="ghost-button" onClick={() => { window.location.hash = 'Projects'; }}>{en.imageImport.browseProjects}</button></p>}
    {projectId && <DatasetWorkspace key={projectId} projectId={projectId} />}
  </section>;
}
