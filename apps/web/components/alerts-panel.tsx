"use client";
import {useEffect, useState} from 'react';
import {dismissAlert, listAlerts, seeAlert, type AlertEvent} from '../lib/api';
export function AlertsPanel() {
  const [alerts, setAlerts] = useState<AlertEvent[] | null>(null); const [error, setError] = useState('');
  const reload = () => listAlerts().then(setAlerts).catch(() => setError('Unable to load alerts. Please retry.'));
  useEffect(() => { void reload(); }, []);
  const act = async (id: string, action: (id: string) => Promise<AlertEvent>) => { try { const changed = await action(id); setAlerts(current => current?.map(a => a.id === id ? changed : a) ?? null); } catch { setError('Alert action failed. Please retry.'); } };
  if (!alerts) return <section aria-label="Alerts"><h2>Alerts</h2>{error ? <p role="alert">{error}</p> : <p role="status">Loading alerts...</p>}</section>;
  return <section aria-label="Alerts"><h2>Alerts</h2>{error && <p role="alert">{error}</p>}{alerts.length === 0 ? <p>No alerts.</p> : <ol>{alerts.map(alert => <li key={alert.id}><p>{alert.severity}</p><p>Question: {alert.question_title}</p><p>{alert.reason}</p><time dateTime={alert.created_at}>{alert.created_at}</time><p>{alert.status}</p>{alert.status === 'new' && <button onClick={() => void act(alert.id, seeAlert)}>Seen</button>}{alert.status !== 'dismissed' && <button onClick={() => void act(alert.id, dismissAlert)}>Dismiss</button>}</li>)}</ol>}</section>;
}
