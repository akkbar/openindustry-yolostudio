import { useEffect, useRef, useState } from 'react';
import { Upload, RefreshCw } from 'lucide-react';
import { ApiError, getImportSummary, importImage, type ImageImportResult } from '../api';
import { APP_LOCALE, en } from '../locales/en';

const copy = en.imageImport;
const number = (value: number) => new Intl.NumberFormat(APP_LOCALE).format(value);
type Failure = { file: File; message: string };

export default function ImageImport({ projectId, refreshToken = 0, onImported }: { projectId: string; refreshToken?: number; onImported?: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const running = useRef(false);
  const lifetime = useRef<AbortController | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [progress, setProgress] = useState({ done: 0, total: 0, imported: 0, duplicate: 0, failed: 0 });
  const [results, setResults] = useState<ImageImportResult[]>([]);
  const [failures, setFailures] = useState<Failure[]>([]);

  const refresh = async (signal?: AbortSignal) => {
    try {
      const summary = await getImportSummary(projectId, signal);
      if (!signal?.aborted) { setCount(summary.image_count); setLoadError(null); }
    } catch (error) {
      if (!signal?.aborted) setLoadError(error instanceof ApiError ? error.message : en.connectionFailure);
    }
  };

  useEffect(() => {
    const controller = new AbortController();
    lifetime.current = controller;
    void refresh(controller.signal);
    return () => { controller.abort(); };
  }, [projectId]);

  useEffect(() => { if (refreshToken) { setResults([]); void refresh(lifetime.current?.signal); } }, [refreshToken]);

  const importFiles = async (files: File[]) => {
    const signal = lifetime.current?.signal;
    if (!files.length || running.current || !signal || signal.aborted) return;
    running.current = true;
    setBusy(true);
    setFailures([]);
    setResults([]);
    setProgress({ done: 0, total: files.length, imported: 0, duplicate: 0, failed: 0 });
    let next = 0;
    const worker = async () => {
      while (next < files.length && !signal.aborted) {
        const file = files[next++];
        try {
          if (!/\.(jpe?g|png|webp)$/i.test(file.name)) throw new Error(copy.unsupported);
          if (file.size > 25 * 1024 * 1024) throw new Error(copy.tooLarge);
          const result = await importImage(projectId, file, signal);
          if (signal.aborted) return;
          setResults(previous => [...previous, result].slice(-20));
          setProgress(previous => ({ ...previous, done: previous.done + 1, [result.status]: previous[result.status] + 1 }));
        } catch (error) {
          if (signal.aborted) return;
          setFailures(previous => [...previous, { file, message: error instanceof Error ? error.message : en.apiFailure }]);
          setProgress(previous => ({ ...previous, done: previous.done + 1, failed: previous.failed + 1 }));
        }
      }
    };
    try { await Promise.all([worker(), worker()]); }
    finally {
      running.current = false;
      if (!signal.aborted) { setBusy(false); onImported?.(); await refresh(signal); }
    }
  };

  return <section className="image-import" aria-label={copy.title}>
    <div className="import-heading"><div><h2>{copy.title}</h2><p>{copy.detail}</p></div>
      {count !== null && <span className="import-count">{copy.count(number(count))}</span>}
    </div>
    {loadError && <div className="field-error" role="alert">{loadError}<button className="ghost-button" onClick={() => void refresh(lifetime.current?.signal)}>{copy.retryLoad}</button></div>}
    <div className={`import-dropzone ${dragging ? 'dragging' : ''} ${busy ? 'busy' : ''}`}
      onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = busy ? 'none' : 'copy'; if (!busy) setDragging(true); }}
      onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setDragging(false); }}
      onDrop={event => { event.preventDefault(); setDragging(false); if (!busy) void importFiles(Array.from(event.dataTransfer.files)); }}>
      <Upload size={30} aria-hidden="true" />
      <h3>{busy ? copy.importing : copy.drop}</h3><p>{copy.limits}</p>
      <input ref={input} type="file" hidden multiple accept=".jpg,.jpeg,.png,.webp" aria-label={copy.input}
        onChange={event => { void importFiles(Array.from(event.target.files ?? [])); event.target.value = ''; }} />
      <button className="primary-button" disabled={busy} onClick={() => input.current?.click()}>{copy.choose}</button>
    </div>
    {progress.total > 0 && <div className="import-progress" aria-live="polite">
      <p>{copy.progress(number(progress.done), number(progress.total))}</p>
      <progress aria-label={copy.importing} value={progress.done} max={progress.total} />
      <p>{copy.results(number(progress.imported), number(progress.duplicate), number(progress.failed))}</p>
    </div>}
    {failures.length > 0 && <section className="import-failures"><h3>{copy.failures}</h3>
      <ul>{failures.map((failure, index) => <li key={index}><strong>{failure.file.name}</strong><span>{failure.message}</span></li>)}</ul>
      <button className="ghost-button" disabled={busy} onClick={() => void importFiles(failures.map(f => f.file))}><RefreshCw size={14} />{copy.retry}</button>
    </section>}
    {results.length > 0 && <section><h3>{copy.recent}</h3><div className="import-results">{results.map((result, index) => <article key={`${result.image.id}-${index}`}>
      <img src={result.image.thumbnail_url} alt={result.image.file_name} width="96" height="80" loading="lazy" />
      <div><strong>{result.image.file_name}</strong><span>{copy[result.status]}</span></div>
    </article>)}</div>{progress.done > 20 && <p className="import-hint">{copy.resultLimit}</p>}</section>}
  </section>;
}
