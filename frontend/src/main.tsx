import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';

function App() {
  const [status, setStatus] = useState('Checking APIâ€¦');
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    fetch('/api/health', { signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw new Error('API unavailable');
        const body: unknown = await response.json();
        if (typeof body !== 'object' || body === null || !('status' in body) || body.status !== 'ok') throw new Error('Invalid health response');
        if (active) setStatus('API connected');
      })
      .catch(() => { setStatus('API unavailable â€” start the backend and retry.'); })
      .finally(() => clearTimeout(timeout));
    return () => { active = false; clearTimeout(timeout); controller.abort(); };
  }, []);
  return <main className="mx-auto max-w-6xl px-6 py-14">
    <header className="border-b border-slate-700 pb-8">
      <p className="text-sm uppercase tracking-widest text-teal-300">Security operations / Foundation</p>
      <h1 className="mt-3 text-4xl font-semibold">KillChain AI</h1>
      <p className="mt-4 max-w-2xl text-slate-300">Trace evidence. Reconstruct attack paths. Understand what could happen next.</p>
      <p role="status" className="mt-5 text-sm text-teal-200">{status}</p>
    </header>
    <section className="mt-10 grid gap-5 md:grid-cols-3" aria-label="Planned capabilities">
      {['Evidence & detection', 'Incident correlation', 'Attack path analysis'].map(title => <article key={title} className="rounded-xl border border-slate-700 bg-slate-900 p-6"><p className="text-xs uppercase tracking-wider text-slate-400">Planned</p><h2 className="mt-3 text-xl">{title}</h2><p className="mt-4 text-sm leading-6 text-slate-400">Awaiting validated data contracts and implementation.</p></article>)}
    </section>
    <section className="mt-8 rounded-xl border border-dashed border-slate-600 p-8"><h2 className="text-xl">No dataset connected</h2><p className="mt-3 text-slate-400">This foundation does not ingest logs, generate detections, or predict targets. Dataset adapters and evidence-backed analysis arrive in later phases.</p></section>
  </main>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
