import {scanMetrics} from './scanMetrics';
export type ScanJob={job_id:string;source_reference:string;source_profile?:string;source_size:number;status:string;records_processed:number;records_accepted:number;records_partial:number;records_rejected:number;bytes_processed:number;elapsed_seconds?:number;checkpoint:{records_processed:number;created_at:string}|null;error:{code:string;message:string}|null};

export function ScanConsole({job,connected}:{job:ScanJob|null;connected:boolean}) {
  const elapsed=job?.elapsed_seconds||0;
  const {percent:percentage,rate,blocks}=scanMetrics(job?.bytes_processed||0,job?.source_size||0,job?.records_processed||0,elapsed,job?.status||'idle');
  const bar='█'.repeat(blocks)+'░'.repeat(20-blocks);
  const phase:Record<string,string>={queued:'Waiting for the local worker',hashing:'Verifying source evidence hash',running:'Reading and validating log records',cancelling:'Finishing checkpoint before cancellation',cancelled:'Scan cancelled; durable checkpoint retained',failed:'Scan stopped with an error',completed:'Log normalization completed; investigation available',interrupted:'Worker interrupted; checkpoint recovery available'};
  return <section className="scan-console" aria-label="Live log scan console">
    <div className="console-title"><span><i/> LOCAL LOG SCANNER</span><span>{connected?'API ONLINE':'API CONNECTING'}</span></div>
    <div className="console-body">
      <p className="console-command"><span>killchain&gt;</span> {job?`scan ${JSON.stringify(job.source_reference)}`:'Select a local log file to begin'}</p>
      <p><span className="console-key">JOB</span> {job?.job_id || '—'}</p>
      <p><span className="console-key">PARSER</span> {job?.source_profile || 'No active source profile'}</p>
      <p role="status"><span className="console-key">STATE</span> {job?phase[job.status]||job.status:'Ready / no scan selected'}</p>
      <p className="console-progress">[{bar}] <strong>{percentage.toFixed(1)}%</strong></p>
      {job&&<><p><span className="console-key">INPUT</span> {(job.bytes_processed/1024**2).toFixed(1)} / {(job.source_size/1024**2).toFixed(1)} MiB read</p><p><span className="console-key">RESULT</span> {job.records_processed.toLocaleString()} records / {job.records_accepted.toLocaleString()} accepted / {job.records_rejected.toLocaleString()} rejected</p><p><span className="console-key">TIME</span> {elapsed.toFixed(1)} s {rate!==null?`/ ${rate.toFixed(0)} records/s average`:''}</p><p><span className="console-key">SAVED</span> {job.checkpoint?`${job.checkpoint.records_processed.toLocaleString()} records at ${job.checkpoint.created_at}`:'No durable checkpoint yet'}</p></>}
      {job?.error&&<p role="alert" className="console-error">{job.error.code}: {job.error.message}</p>}
      {!!job?.records_partial&&<p className="console-note">{job.records_partial.toLocaleString()} accepted records have validation issues; these are included in the accepted count above.</p>}
      {job?.source_profile==='raw-text-1.0.0'&&<p className="console-note">Raw-text mode preserves messages. Detection requires a supported structured source profile; changing the format selector does not alter this running job.</p>}
      <p className="console-note">Progress comes from the worker’s reported byte offsets. Updates arrive at checkpoints. Hashing and rule evaluation may take time without advancing this bar.</p>
    </div>
  </section>;
}
