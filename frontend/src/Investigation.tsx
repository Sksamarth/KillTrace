import { lazy, Suspense, useEffect, useState } from 'react';
import type { GraphNode, GraphEdge } from './AttackGraph';
const AttackGraph=lazy(()=>import('./AttackGraph').then(module=>({default:module.AttackGraph})));

type Status = {status:string; stage?:string; records_scanned?:number; detections?:number; incidents?:number; source_alerts?:number; synthetic?:boolean; supported_observations?:number; error?:{message:string}};
type Incident = {id:string;actor:string;detections:number;matched_observations:number};
type Step = {id:string;rule_id:string;started:number;technique:string;technique_name:string;tactic:string;kill_chain_stage:string|null;count:number;conclusion:string;evidence:unknown[]};
type Path = {timeline:Step[];truncated:boolean;interpretation:string;nodes:GraphNode[];edges:GraphEdge[]};
async function request<T>(path:string, post=false):Promise<T> {
  const response=await fetch('/api/investigations/'+path,{method:post?'POST':'GET'});
  let data;
  try{data=await response.json();}catch{throw new Error('Local API temporarily unavailable. Retry when it reconnects.');}
  if(!response.ok) throw new Error(data.detail || 'Investigation request failed');
  return data;
}

export function Investigation({jobId,totalRecords,managed=false}:{jobId:string;totalRecords:number;managed?:boolean}) {
  const [status,setStatus]=useState<Status>({status:'loading'});
  const [incidents,setIncidents]=useState<Incident[]>([]);
  const [path,setPath]=useState<Path|null>(null);
  const [observed,setObserved]=useState<{nodes:GraphNode[];edges:GraphEdge[];interpretation:string}|null>(null);
  const [error,setError]=useState('');
  const [pollError,setPollError]=useState('');
  const [raw,setRaw]=useState('');
  const [offset,setOffset]=useState(0);
  useEffect(()=>{
    let live=true;
    const refresh=()=>{ void request<Status>(jobId).then(data=>{if(live){setStatus(data);setPollError('');}}).catch(e=>{if(live)setPollError(String(e));}); };
    refresh(); const timer=setInterval(refresh,2000);
    return ()=>{live=false;clearInterval(timer);};
  },[jobId]);
  useEffect(()=>{
    if(status.status!=='completed')return;
    let live=true;
    void request<{items:Incident[]}>(`${jobId}/incidents?offset=${offset}&limit=20`).then(data=>{if(live){setIncidents(data.items);if(!path&&data.items.length)void request<Path>(`${jobId}/incidents/${data.items[0].id}/path`).then(result=>{if(live)setPath(result);}).catch(e=>{if(live)setError(String(e));});}}).catch(e=>{if(live)setError(String(e));});
    return ()=>{live=false;};
  },[jobId,status.status,offset]);
  useEffect(()=>{
    if(status.status!=='completed')return;
    let live=true;
    void request<{nodes:GraphNode[];edges:GraphEdge[];interpretation:string}>(`${jobId}/observed-graph`).then(data=>{if(live)setObserved(data);}).catch(e=>{if(live)setError(String(e));});
    return()=>{live=false;};
  },[jobId,status.status]);
  async function start(){try{setError('');setStatus(await request<Status>(jobId,true));}catch(e){setError(String(e));}}
  async function open(id:string){try{setRaw('');setPath(await request<Path>(`${jobId}/incidents/${id}/path`));}catch(e){setError(String(e));}}
  async function evidence(id:string){try{const data=await request<{raw:string}>(`${jobId}/detections/${id}/evidence/0`);setRaw(data.raw);}catch(e){setError(String(e));}}
  const readProgress=totalRecords?Math.min(100,100*(status.records_scanned||0)/totalRecords):0;
  return <section className="investigation-panel mt-8 rounded-xl border border-teal-800 bg-slate-900 p-6">
    <h2 className="text-2xl">Rule analysis / attack graph</h2>
    <p className="mt-2 text-sm text-slate-300">Run evidence-based rules, group related findings, and inspect their timeline and entity graph. Findings are investigation candidates; shared entities do not prove attacker movement.</p>
    <p className="mt-3" role="status">Analysis: {status.status}{status.records_scanned!==undefined?` / ${status.records_scanned.toLocaleString()} records scanned`:''}</p>
    {status.status==='running'&&<div className="analysis-progress"><p>{status.stage?.replaceAll('_',' ')||'Processing evidence'} / event read pass: {readProgress.toFixed(1)}%</p><progress aria-label="Analysis event read progress" max={100} value={readProgress}/><small>Rule evaluation and correlation continue after the read pass completes.</small></div>}
    {status.synthetic&&<p className="mt-2 text-amber-200">Synthetic input: these findings describe test telemetry, not a real-world incident.</p>}
    {status.status==='not_started'&&(managed?<p className="mt-3 text-sm">The scan worker is preparing rule analysis…</p>:<button onClick={()=>{void start();}} className="mt-3 rounded bg-teal-300 px-5 py-3 text-slate-950">Evaluate rules &amp; build graph</button>)}
    {(error||pollError||status.error)&&<p role="alert" className="mt-3 text-red-300">{error||pollError||status.error?.message}</p>}
    {status.status==='completed'&&<>
      <p className="mt-3">{status.detections} detections · {status.incidents} candidate incidents · {status.source_alerts} source-reported alerts (counted separately)</p>
      {status.supported_observations===0&&<p className="mt-2 text-amber-200">This source profile has no analysis field mapping yet. Raw-text preservation alone does not enable these rules.</p>}
      {incidents.length===0&&<p className="mt-3 text-slate-300">No incidents match the configured rules in this data. This does not establish that the source is attack-free.</p>}
      <div className="mt-4 flex flex-wrap gap-2">{incidents.map(incident=><button key={incident.id} onClick={()=>{void open(incident.id);}} className="rounded border border-slate-600 p-3 text-left">{incident.actor}<br/><span className="text-sm text-slate-400">{incident.detections} findings · {incident.matched_observations} matched observations</span></button>)}</div>
      <div className="mt-3 flex gap-4"><button disabled={offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous</button><button disabled={incidents.length<20} onClick={()=>setOffset(offset+20)}>Next</button></div>
    </>}
    {!path&&observed&&<div className="mt-6"><h3>Observed log relationships</h3><p className="console-note">{observed.interpretation}</p>{observed.nodes.length?<Suspense fallback={<p>Loading graph renderer…</p>}><AttackGraph nodes={observed.nodes} edges={observed.edges} onEvidence={()=>{}}/></Suspense>:<p className="console-note">No mapped network endpoints are available for this graph.</p>}</div>}
    {path&&<div className="mt-6">
      <h3 className="text-xl">Interactive evidence graph</h3>
      <Suspense fallback={<p role="status">Loading graph renderer…</p>}><AttackGraph nodes={path.nodes} edges={path.edges} onEvidence={id=>{void evidence(id);}}/></Suspense>
      <h3 className="text-xl">Incident timeline</h3><p className="mt-2 text-sm text-amber-200">{path.interpretation}</p>
      {path.truncated&&<p>Showing the first 100 findings.</p>}
      <ol className="mt-4 space-y-3">{path.timeline.map(step=><li key={step.id} className="rounded border border-slate-700 p-4"><time>{new Date(step.started*1000).toISOString()}</time><p className="mt-1 text-teal-200">{step.rule_id} · {step.count} observations</p><p className="text-sm">ATT&amp;CK hypothesis: {step.technique} {step.technique_name} / {step.tactic}</p><p className="text-sm">Kill Chain: {step.kill_chain_stage || 'Undetermined from available evidence'}</p><p className="mt-1 text-sm text-slate-400">{step.conclusion}</p><button className="mt-2 underline" disabled={!step.evidence.length} onClick={()=>{void evidence(step.id);}}>View original evidence (hash verified)</button></li>)}</ol>
      <p className="mt-3 text-sm text-slate-400">Next-target analysis is unavailable until asset connectivity and account permissions are supplied.</p>
    </div>}
    {raw&&<div className="mt-5"><h3>Original evidence</h3><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded bg-slate-950 p-4 text-xs">{raw}</pre></div>}
  </section>;
}
