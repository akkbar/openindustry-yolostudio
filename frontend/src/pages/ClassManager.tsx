import { useState } from 'react';
import type { ProjectClass } from '../api';
import Dialog from '../components/Dialog';
import { APP_LOCALE, en } from '../locales/en';
import { useProjectClasses } from '../state/ProjectClasses';

const copy = en.classes;
const number = (value: number) => new Intl.NumberFormat(APP_LOCALE).format(value);

function ClassForm({ item, onClose }: { item: ProjectClass | null; onClose: () => void }) {
  const state = useProjectClasses();
  const [name, setName] = useState(item?.name ?? '');
  const save = async () => {
    if (!name.trim() || state.busy) return;
    if (await (item ? state.rename(item.id, name) : state.add(name))) onClose();
  };
  return <Dialog title={item ? copy.renameTitle : copy.add} busy={state.busy} onClose={onClose}>
    <form onSubmit={event => { event.preventDefault(); void save(); }}>
      <label className="field"><span>{copy.name}</span><input autoFocus value={name} maxLength={80} placeholder={copy.placeholder} onChange={event => setName(event.target.value)} disabled={state.busy} /></label>
      {state.error && <p role="alert" className="field-error">{state.error}</p>}
      <div className="modal-actions"><button type="button" className="ghost-button" disabled={state.busy} onClick={onClose}>{copy.cancel}</button>
        <button className="primary-button" disabled={!name.trim() || state.busy}>{state.busy ? copy.saving : item ? copy.save : copy.add}</button></div>
    </form>
  </Dialog>;
}

export default function ClassManager() {
  const state = useProjectClasses();
  const [editing, setEditing] = useState<ProjectClass | null | undefined>(undefined);
  const [deleting, setDeleting] = useState<ProjectClass | null>(null);
  const disabled = state.busy || state.loading;
  return <aside className="class-manager" aria-label={copy.title}>
    <h2>{copy.title}</h2><p>{copy.detail}</p>
    {state.loading && <p aria-live="polite">{copy.loading}</p>}
    {state.error && editing === undefined && !deleting && <p className="field-error" role="alert">{state.error}</p>}
    <button className="ghost-button" disabled={disabled} onClick={() => void state.refresh()}>{copy.retry}</button>
    {!state.loading && state.data && <>
      <p className="active-class" aria-live="polite">{copy.active}: <strong>{state.selectedClass ? `${number(state.selectedClass.class_index)} · ${state.selectedClass.name}` : copy.none}</strong></p>
      {!state.data.classes.length ? <p>{copy.empty}</p> : <ul className="class-list">{state.data.classes.map(item => <li className="class-row" key={item.id}>
        <button className="class-select" aria-label={copy.select(item.name)} aria-pressed={state.data?.selected_class_id === item.id} disabled={disabled} onClick={() => void state.select(item.id)}>
          <span className="class-swatch" style={{ backgroundColor: item.color }} aria-hidden="true" /><span className="class-index">{number(item.class_index)}</span><strong>{item.name}</strong></button>
        {Boolean(item.annotation_count) && <span className="class-used">{copy.inUse}</span>}
        <div className="class-actions"><button className="ghost-button" aria-label={copy.rename(item.name)} disabled={disabled} onClick={() => { state.clearError(); setEditing(item); }}>{en.projects.rename}</button>
          <button className="ghost-button" aria-label={copy.remove(item.name)} disabled={disabled} onClick={() => { state.clearError(); setDeleting(item); }}>{en.projects.remove}</button></div>
      </li>)}</ul>}
      <div className="class-toolbar"><button className="primary-button" disabled={disabled} onClick={() => { state.clearError(); setEditing(null); }}>{copy.add}</button>
        {state.selectedClass && <button className="ghost-button" disabled={disabled} onClick={() => void state.select(null)}>{copy.clear}</button>}</div>
    </>}
    {editing !== undefined && <ClassForm item={editing} onClose={() => setEditing(undefined)} />}
    {deleting && <Dialog title={copy.deleteTitle} busy={state.busy} onClose={() => setDeleting(null)}>
      <p className="gallery-file-name">{copy.deleteDetail(deleting.name)}</p>
      {state.error && <p role="alert" className="field-error">{state.error}</p>}
      <div className="modal-actions"><button className="ghost-button" autoFocus disabled={state.busy} onClick={() => setDeleting(null)}>{copy.cancel}</button>
        <button className="danger-button" disabled={state.busy} onClick={async () => { if (await state.remove(deleting.id)) setDeleting(null); }}>{state.busy ? copy.deleting : copy.confirm}</button></div>
    </Dialog>}
  </aside>;
}
