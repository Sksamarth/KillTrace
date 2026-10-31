import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

type Checkpoint = { records_processed: number; bytes_processed: number; parquet_parts: number; created_at: string };
type Job = { job_id: string; source_reference: string; source_size: number; status: string; records_processed: number; records_accepted: number; records_partial: number; records_rejected: number; bytes_processed: number; attempt: number; started_at: string | null; completed_at: string | null; checkpoint: Checkpoint | null; error: { code: string; message: string } | null; last_validation_issue?: { issues: string[]; record_number: number }; elapsed_seconds?: number };
type Source = { reference: string; bytes: number };
const active = new Set(['queued', 'hashing', 'running', 'cancelling']);
const issueHelp: Record<string, string> = {
  malformed_json_or_encoding: 'Record is not valid UTF-8 JSON.',
  record_not_object: 'Record is not a JSON object.',
  invalid_source_fields: 'A mapped field has an invalid type, address or value range.',
  invalid_source_field_type: 'A mapped object has the wrong structure.',
  timestamp_invalid: 'Timestamp cannot be parsed; its original value is preserved.',
  timestamp_missing: 'No usable timestamp was supplied; an occurrence time was not invented.',
  timestamp_explicit_null: 'The source timestamp is explicitly null.',
  timestamp_offset_unknown: 'Timezone offset is missing; UTC was not guessed.',
  record_too_large: 'Record exceeds the approved 1 MiB limit; its full source span is retained.',
  record_exceeds_batch_budget: 'Record cannot fit the configured batch budget.',
};
async function api<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch('/api/ingestion' + path, { method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? undefined : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal });
  if (!response.ok) {
    let message = `Request failed (${response.status}). Check the backend server.`;
    try { const error = await response.json(); if (typeof error.detail === 'string') message = error.detail; } catch { /* a proxy error may have no JSON body */ }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
function App() {
  const [sources, setSources] = useState<Source[]>([]);
  const [reference, setReference] = useState('');
  const [profile, setProfile] = useState('raw-text-1.0.0');
  const [synthetic, setSynthetic] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const [error, setError] = useState('');
  const [connectionError, setConnectionError] = useState('');
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [config, setConfig] = useState<Record<string, number>>({});
  useEffect(() => {
    const controller = new AbortController();
    const load = () => { void api<{ items: Source[]; configuration: Record<string, number> }>('/sources', undefined, controller.signal)
      .then(data => { setSources(data.items); setConfig(data.configuration); setConnected(true); clearInterval(timer); })
      .catch(e => { if (!controller.signal.aborted) { setConnected(false); setConnectionError(String(e)); } }); };
    const timer = setInterval(load, 3000);
    load();
    return () => { clearInterval(timer); controller.abort(); };
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      void api<{ items: Job[] }>('/jobs?limit=20', undefined, controller.signal).then(data => { setJobs(data.items); setConnected(true); setConnectionError(''); }).catch(e => { if (!controller.signal.aborted) { setConnected(false); setConnectionError(String(e)); } });
      if (selectedId) void api<Job>(`/jobs/${selectedId}`, undefined, controller.signal).then(setSelected).catch(e => { if (!controller.signal.aborted) setConnectionError(String(e)); });
    };
    refresh();
    const timer = setInterval(refresh, 2000);
    return () => { clearInterval(timer); controller.abort(); };
  }, [selectedId]);
  async function start() {
    setBusy(true); setError('');
    try { const job = await api<Job>('/jobs', { source: reference, source_profile: profile, synthetic: synthetic || profile === 'simedr-json-1.0.0' }); setSelectedId(job.job_id); setSelected(job); setJobs(items => [job, ...items.filter(item => item.job_id !== job.job_id)].slice(0, 20)); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function action(kind: 'cancel' | 'resume') {
    if (!selectedId) return;
    setBusy(true); setError('');
    try { setSelected(await api<Job>(`/jobs/${selectedId}/${kind}`, {})); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const hasActiveJob = jobs.some(job => active.has(job.status));
  const percentage = selected?.source_size ? Math.min(100, (selected.bytes_processed / selected.source_size) * 100) : 0;
  return <main className="mx-auto max-w-6xl px-6 py-12">
    <header className="border-b border-slate-700 pb-7"><p className="text-xs uppercase tracking-widest text-teal-300">Security log ingestion / Chunk 3</p><h1 className="mt-3 text-4xl font-semibold">KillChain AI</h1><p className="mt-4 max-w-3xl text-slate-300">Validate records, preserve evidence and write canonical Parquet with bounded working sets.</p><p role="status" className="mt-4 text-sm text-teal-200">{connected ? 'Local API connected' : 'Connecting to the local API...'}</p></header>
    {(error || connectionError) && <p role="alert" className="mt-5 rounded-lg border border-red-700 bg-red-950 p-4 text-red-200">{error || connectionError}</p>}
    <section className="mt-7 rounded-xl border border-slate-700 bg-slate-900 p-6"><h2 className="text-xl">Start ingestion</h2><p className="mt-2 text-sm leading-6 text-slate-400">Supported: raw UTF-8 text, quoted key=value records, generic JSON objects, standard combined web access logs, and existing SimEDR JSON Lines. Select a local file or provide a relative path under the configured input directory. Files stay on this computer.</p>
      <label className="mt-4 block text-sm">Source format<select className="ml-3 rounded border border-slate-600 bg-slate-950 p-2" value={profile} onChange={event => setProfile(event.target.value)}><option value="raw-text-1.0.0">Raw text / application or server log (preserve messages)</option><option value="firex-kv-1.0.0">FireX typed security logs</option><option value="key-value-1.0.0">Generic key=value logs</option><option value="json-record-1.0.0">Generic JSON Lines objects</option><option value="web-combined-1.0.0">Apache/Nginx combined access log</option><option value="simedr-json-1.0.0">Synthetic SimEDR JSON Lines</option></select></label><div className="mt-5 grid gap-4 md:grid-cols-2"><label className="text-sm">Available local sources<select className="mt-2 block w-full rounded border border-slate-600 bg-slate-950 p-3" value={sources.some(source => source.reference === reference) ? reference : ''} onChange={event => setReference(event.target.value)}><option value="">Choose a source</option>{sources.map(source => <option key={source.reference} value={source.reference}>{source.reference} ({(source.bytes / 1024**2).toFixed(1)} MiB)</option>)}</select></label><label className="text-sm">Relative input path<input className="mt-2 block w-full rounded border border-slate-600 bg-slate-950 p-3" value={reference} onChange={event => setReference(event.target.value)} placeholder="simedr-1gib.jsonl" /></label></div>
      <label className="mt-5 flex items-start gap-3 text-sm text-slate-300"><input type="checkbox" checked={acknowledged} onChange={event => setAcknowledged(event.target.checked)} className="mt-1" />I am authorized to process this file using the selected source format.</label>
      <label className="mt-3 flex gap-3 text-sm text-slate-300"><input type="checkbox" checked={synthetic} onChange={event => setSynthetic(event.target.checked)} />Mark this input as synthetic/test data (SimEDR is always synthetic).</label><button className="mt-5 rounded bg-teal-300 px-5 py-3 font-medium text-slate-950" disabled={!connected || busy || hasActiveJob || !reference || !acknowledged} onClick={() => { void start(); }}>Start ingestion</button>
      {hasActiveJob && <p className="mt-3 text-sm text-amber-200">A worker is already active. Select its job to inspect progress or request cancellation.</p>}
      <p className="mt-4 text-xs text-slate-400">Configured batch: {config.ingestion_batch_rows || '-'} rows / {config.ingestion_batch_bytes ? (config.ingestion_batch_bytes / 1024**2).toFixed(1) : '-'} MiB estimated payload. Memory admission: {config.ingestion_memory_mb || '-'} MiB; actual allocations are checked between records and batches.</p>
    </section>
    <div className="mt-7 grid gap-6 lg:grid-cols-[320px_1fr]"><section><h2 className="mb-4 text-xl">Recent jobs</h2>{jobs.length === 0 && <p className="rounded border border-dashed border-slate-600 p-6 text-slate-400">No ingestion jobs yet.</p>}{jobs.map(job => <button className={`mb-3 w-full rounded-lg border p-4 text-left ${selectedId === job.job_id ? 'border-teal-400 bg-teal-950' : 'border-slate-700 bg-slate-900'}`} key={job.job_id} onClick={() => { setSelectedId(job.job_id); setSelected(job); setError(''); }}><p className="font-medium">{job.source_reference}</p><p className="mt-2 text-sm text-teal-200">{job.status} / {job.records_processed.toLocaleString()} records</p><p className="mt-2 truncate text-xs text-slate-400">{job.job_id}</p></button>)}</section>
      <section className="rounded-xl border border-slate-700 p-6">{!selected ? <p className="text-slate-400">Select a job to see validation outcomes, progress and its last durable checkpoint.</p> : <><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl">Job: {selected.status}</h2><p className="text-sm text-slate-400">Attempt {selected.attempt}</p></div><p className="mt-2 break-all text-xs text-slate-400">{selected.job_id}</p><progress max={100} value={percentage} className="mt-6 h-3 w-full accent-teal-300" aria-label="Bytes processed"/><p className="mt-2 text-sm text-slate-300">{percentage.toFixed(1)}% / {(selected.bytes_processed / 1024**2).toFixed(1)} MiB of {(selected.source_size / 1024**2).toFixed(1)} MiB</p>
        <dl className="mt-6 grid grid-cols-2 gap-4">{[['Processed', selected.records_processed], ['Accepted', selected.records_accepted], ['Partially accepted (included above)', selected.records_partial], ['Rejected', selected.records_rejected]].map(([label, count]) => <div key={label} className="rounded border border-slate-700 bg-slate-900 p-4"><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-2 text-2xl">{Number(count).toLocaleString()}</dd></div>)}</dl>
        {selected.error && <p className="mt-5 break-words rounded border border-red-800 p-4 text-sm text-red-200">{selected.error.code}: {selected.error.message}</p>}
        {selected.last_validation_issue && <p className="mt-5 text-sm text-amber-200">Latest validation outcome: line {selected.last_validation_issue.record_number}, {selected.last_validation_issue.issues.map(code => issueHelp[code] || code).join(' ')}. Raw bytes remain referenced in the validation ledger.</p>}
        {(selected.records_partial > 0 || selected.records_rejected > 0) && <a className="mt-4 inline-block text-sm text-teal-300 underline" href={`/api/ingestion/jobs/${selected.job_id}/validation?limit=50`} target="_blank" rel="noreferrer">View durable validation entries</a>}{selected.error?.code === 'SourceChanged' && <p className="mt-4 text-sm text-amber-200">The source changed. Start a new job with verified input; this checkpoint cannot be reused.</p>}<section className="mt-6 rounded border border-slate-700 p-4"><h3 className="font-medium">Durable checkpoint</h3>{selected.checkpoint ? <p className="mt-2 text-sm leading-6 text-slate-400">{selected.checkpoint.records_processed.toLocaleString()} records / {selected.checkpoint.parquet_parts} partition files. Updated {selected.checkpoint.created_at}. Recovery rechecks the original file hash and resumes at the saved byte offset.</p> : <p className="mt-2 text-sm text-slate-400">No durable checkpoint yet; hashing or startup may still be in progress.</p>}</section>
        <div className="mt-6 flex flex-wrap gap-3">{active.has(selected.status) && <button className="rounded border border-amber-500 px-4 py-2 text-amber-200" disabled={busy || selected.status === 'cancelling'} onClick={() => { void action('cancel'); }}>Request cancellation</button>}{['failed', 'cancelled', 'interrupted'].includes(selected.status) && selected.error?.code !== 'SourceChanged' && <button className="rounded bg-teal-300 px-4 py-2 text-slate-950" disabled={busy || hasActiveJob} onClick={() => { void action('resume'); }}>Resume from checkpoint</button>}</div><p className="mt-5 text-xs leading-5 text-slate-500">Cancellation is cooperative. A bounded batch finishes its checkpoint before stopping. A failed attempt can show attempted counters beyond its last durable checkpoint; recovery starts from that checkpoint.</p>
      </>}</section></div>
    <footer className="mt-8 border-t border-slate-800 pt-5 text-xs text-slate-500">This phase performs ingestion and validation only. Detection, ATT&CK mapping, graphs, correlation and AI remain future work.</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
