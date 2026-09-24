"use client";
import {useEffect, useState} from 'react';
import {disableMonitoring, enableMonitoring, getMonitoring, monitorNow, type MonitoringStatus} from '../lib/api';

export function MonitoringPanel({questionId}: {questionId: string}) {
  const [data, setData] = useState<MonitoringStatus | null>(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState('');
  const [pending, setPending] = useState('');
  const reload = async () => { try { setLoadError(''); setData(await getMonitoring(questionId)); } catch { setLoadError('Unable to load monitoring. Please retry.'); setData({id: '', enabled: false, monitoring_interval_minutes: 360, last_run_at: null, last_success_at: null, next_run_at: null, latest_run: null}); } };
  useEffect(() => { void reload(); }, [questionId]);
  const act = async (kind: string, action: () => Promise<unknown>) => { setPending(kind); setError(''); try { await action(); await reload(); } catch { setError('Monitoring action failed. Please retry.'); } finally {setPending('');} };
  if (!data) return <section aria-label="Monitoring"><h2>Monitoring</h2><p role="status">Loading monitoring...</p></section>;
  return <section aria-label="Monitoring"><h2>Monitoring</h2>
    <p>{data.enabled ? 'Monitoring is enabled' : 'Monitoring is disabled'}</p>
    <p>Last checked: {data.last_run_at ?? 'Never checked'}</p><p>Next check: {data.next_run_at ?? 'Not scheduled'}</p>
    {data.latest_run && <><p>Latest run: {data.latest_run.status}</p><p>Latest findings: {data.latest_run.normalized_findings ?? 0}</p><p>Latest candidates: {data.latest_run.candidates_created ?? 0}</p></>}{data.latest_run?.safe_error_summary && <p role="alert">{data.latest_run.safe_error_summary}</p>}
    {loadError && <p role="status">{loadError}</p>}{error && <p role="alert">{error}</p>}
    {data.enabled ? <><button disabled={!!pending} onClick={() => act('run', () => monitorNow(questionId))}>{pending === 'run' ? 'Monitoring…' : 'Monitor now'}</button><button disabled={!!pending} onClick={() => act('disable', () => disableMonitoring(questionId))}>Disable monitoring</button></> : <button disabled={!!pending} onClick={() => act('enable', () => enableMonitoring(questionId))}>{pending === 'enable' ? 'Enabling…' : 'Enable monitoring'}</button>}
  </section>;
}
