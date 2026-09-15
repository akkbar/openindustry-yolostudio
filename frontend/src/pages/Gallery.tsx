import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiError, deleteImage, listImages, type GalleryImage, type ImagePage } from '../api';
import { APP_LOCALE, en } from '../locales/en';

const copy = en.gallery;
const number = (value: number) => new Intl.NumberFormat(APP_LOCALE).format(value);
const dimensions = (image: GalleryImage) => copy.dimensions(number(image.width), number(image.height));
const describe = (error: unknown) => error instanceof ApiError ? error.message : en.connectionFailure;

function Dialog({ title, busy = false, onClose, children }: { title: string; busy?: boolean; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current!;
    const previous = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => { dialog.close(); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <dialog className="gallery-dialog" ref={ref} aria-label={title} onCancel={event => { event.preventDefault(); if (!busy) onClose(); }}>
    <h2>{title}</h2>{children}
  </dialog>;
}

function Preview({ image, onClose }: { image: GalleryImage; onClose: () => void }) {
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  return <Dialog title={copy.preview} onClose={onClose}>
    <p className="gallery-file-name">{image.file_name}</p>
    <p>{dimensions(image)} · {image.annotated ? copy.annotated : copy.notAnnotated}</p>
    {failed ? <p role="alert">{copy.unavailable} <button className="ghost-button" onClick={() => { setFailed(false); setAttempt(value => value + 1); }}>{copy.retry}</button></p>
      : <img key={attempt} className="gallery-original" src={`${image.original_url}?attempt=${attempt}`} alt={image.file_name} onError={() => setFailed(true)} />}
    <div className="modal-actions"><button className="primary-button" autoFocus onClick={onClose}>{copy.close}</button></div>
  </Dialog>;
}

function ConfirmDelete({ projectId, image, onClose, onDeleted }: { projectId: string; image: GalleryImage; onClose: () => void; onDeleted: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const confirm = async () => {
    setBusy(true); setError(null);
    try { await deleteImage(projectId, image.id); onDeleted(); }
    catch (failure) {
      // Another window may already have deleted the image. Refresh the gallery.
      if (failure instanceof ApiError && failure.code === 'image_not_found') { onDeleted(); return; }
      setError(describe(failure)); setBusy(false);
    }
  };
  return <Dialog title={copy.deleteTitle} busy={busy} onClose={onClose}>
    <p className="gallery-file-name">{copy.deleteDetail(image.file_name)}</p>
    {error && <p role="alert" className="field-error">{error}</p>}
    <div className="modal-actions"><button className="ghost-button" autoFocus disabled={busy} onClick={onClose}>{copy.cancel}</button>
      <button className="danger-button" disabled={busy} onClick={() => void confirm()}>{busy ? copy.deleting : copy.confirm}</button></div>
  </Dialog>;
}

function Thumbnail({ image }: { image: GalleryImage }) {
  const [failed, setFailed] = useState(false);
  return failed ? <span className="gallery-thumbnail-failed">{copy.unavailable}</span>
    : <img src={image.thumbnail_url} alt="" loading="lazy" decoding="async" width="256" height="160" onError={() => setFailed(true)} />;
}

export default function Gallery({ projectId, refreshToken, onDeleted }: { projectId: string; refreshToken: number; onDeleted: () => void }) {
  const [offset, setOffset] = useState(0);
  const [reload, setReload] = useState(0);
  const [page, setPage] = useState<ImagePage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [preview, setPreview] = useState<GalleryImage | null>(null);
  const [deleting, setDeleting] = useState<GalleryImage | null>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null);
    void listImages(projectId, offset, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      if (offset > 0 && offset >= result.total) { setOffset(Math.max(0, Math.floor((result.total - 1) / 60) * 60)); return; }
      setPage(result); setLoading(false);
    }).catch(failure => { if (!controller.signal.aborted) { setError(describe(failure)); setLoading(false); } });
    return () => controller.abort();
  }, [projectId, offset, refreshToken, reload]);
  const turnPage = (next: number) => { setOffset(next); heading.current?.focus({ preventScroll: true }); heading.current?.scrollIntoView({ block: 'start' }); };
  return <section className="dataset-gallery" aria-label={copy.title}>
    <div className="gallery-heading"><div><h2 ref={heading} tabIndex={-1}>{copy.title}</h2><p>{copy.detail}</p></div>
      <button className="ghost-button" disabled={loading} onClick={() => setReload(value => value + 1)}>{copy.refresh}</button></div>
    {loading && <p aria-live="polite">{copy.loading}</p>}
    {error && <p role="alert" className="field-error">{error} <button className="ghost-button" onClick={() => setReload(value => value + 1)}>{copy.retry}</button></p>}
    {!loading && !error && page && <>
      {page.total === 0 ? <p>{copy.empty}</p> : <>
        <p aria-live="polite">{copy.range(number(offset + 1), number(offset + page.images.length), number(page.total))}</p>
        <div className="gallery-grid">{page.images.map(image => <article className="gallery-card" key={image.id}>
          <button className="gallery-open" aria-label={copy.open(image.file_name)} onClick={() => setPreview(image)}><Thumbnail image={image} /><strong title={image.file_name}>{image.file_name}</strong></button>
          <p>{dimensions(image)}</p><span className={`annotation-status ${image.annotated ? 'annotated' : ''}`}>{image.annotated ? copy.annotated : copy.notAnnotated}</span>
          <button className="ghost-button" aria-label={copy.remove(image.file_name)} onClick={() => setDeleting(image)}>{en.projects.remove}</button>
        </article>)}</div>
        <div className="gallery-pagination"><button className="ghost-button" disabled={offset === 0} onClick={() => turnPage(Math.max(0, offset - 60))}>{copy.previous}</button>
          <button className="ghost-button" disabled={offset + page.images.length >= page.total} onClick={() => turnPage(offset + 60)}>{copy.next}</button></div>
      </>}
    </>}
    {preview && <Preview image={preview} onClose={() => setPreview(null)} />}
    {deleting && <ConfirmDelete projectId={projectId} image={deleting} onClose={() => setDeleting(null)} onDeleted={() => { setDeleting(null); setReload(value => value + 1); onDeleted(); heading.current?.focus(); }} />}
  </section>;
}
