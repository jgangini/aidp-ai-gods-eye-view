import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { GodsEyeViewAdmin } from './GodsEyeViewAdmin';
import './controls.css';

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...options, credentials: 'same-origin', headers: { 'Content-Type': 'application/json', ...options.headers } });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : result.detail?.message || `Request failed (${response.status})`);
  return result;
}

function Controls() {
  const [state, setState] = useState('loading');
  useEffect(() => {
    const controller = new AbortController();
    api('/api/admin/session', { signal: controller.signal }).then(() => setState('admin')).catch(error => { if (!controller.signal.aborted) setState(error.message); });
    return () => controller.abort();
  }, []);
  if (state === 'loading') return <p role="status">Checking administration access…</p>;
  if (state !== 'admin') return <p role="alert">Administration access unavailable: {state}</p>;
  return <GodsEyeViewAdmin api={api} timeZone={Intl.DateTimeFormat().resolvedOptions().timeZone} viewerUrlControl={null} searchIcon={<span aria-hidden="true">Search</span>} refreshIcon={<span aria-hidden="true">Refresh</span>} />;
}

createRoot(document.getElementById('root')!).render(<StrictMode><Controls /></StrictMode>);
