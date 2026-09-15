import { useState } from 'react';
import { ApiError, exportDataset, validateDataset, type DatasetValidation, type DatasetExportResult } from '../api';
import { en } from '../locales/en';

export default function DatasetExport({ projectId }: { projectId: string }) {
  const [report, setReport] = useState<DatasetValidation | null>(null);
  const [result, setResult] = useState<DatasetExportResult | null>(null);
  const [busy, setBusy] = useState<'validate' | 'export' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const copy = en.datasetExport;
  async function run(action: 'validate' | 'export') {
    setBusy(action); setError(null); setReport(null); setResult(null);
    try {
      if (action === 'validate') setReport(await validateDataset(projectId));
      else { const response = await exportDataset(projectId); setReport(response.validation); setResult(response); }
    } catch (failure) { setError(failure instanceof ApiError ? failure.message : en.connectionFailure); }
    finally { setBusy(null); }
  }
  return <section className="dataset-export" aria-labelledby="dataset-export-title" aria-busy={!!busy}>
    <h2 id="dataset-export-title">{copy.title}</h2>
    <p>{copy.detail}</p><p>{copy.policy}</p>
    <div className="dataset-export-actions">
      <button className="ghost-button" disabled={!!busy} onClick={() => void run('validate')}>{copy.validate}</button>
      <button className="primary-button" disabled={!!busy} onClick={() => void run('export')}>{copy.export}</button>
    </div>
    {busy && <p role="status">{busy === 'validate' ? copy.validating : copy.exporting}</p>}
    {error && <p className="field-error" role="alert">{error}</p>}
    {report && <div className="dataset-validation-result">
      <div role="status"><h3>{report.valid ? copy.valid : copy.invalid}</h3></div>
      <dl className="dataset-validation-counts">{(['images', 'annotations', 'classes'] as const).map(key => <div key={key}><dt>{copy[key]}</dt><dd>{report[key].toLocaleString('en-US')}</dd></div>)}</dl>
      <p>{copy.snapshot}</p>
      {!!report.issue_count && <><h4>{copy.issues(report.issue_count)}</h4><ul className="dataset-validation-issues">{report.issues.map((issue, index) => <li key={index}>{issue.file_name && <strong>{issue.file_name}: </strong>}{issue.message}</li>)}</ul>{report.issue_count > report.issues.length && <p>{copy.truncated}</p>}</>}
    </div>}
    {result?.exported && <div className="dataset-export-result">
      <div role="status"><h3>{copy.complete}</h3></div><p>{copy.split(result.train_images!, result.val_images!)}</p>
      <label className="field"><span>{copy.path}</span><input readOnly value={result.path} onFocus={event => event.target.select()} /></label>
      <label className="field"><span>{copy.yaml}</span><input readOnly value={result.yaml_path} onFocus={event => event.target.select()} /></label>
      <p>{copy.saved}</p>
    </div>}
  </section>;
}
