"use client";
import {useEffect, useState} from 'react';
import {listNotificationAttempts, listNotificationPreferences, saveNotificationPreferences, type NotificationAttempt, type NotificationPreference} from '../lib/api';
const defaults = {enabled:false, immediate_alerts_enabled:false, digest_enabled:false};
export function NotificationPanel() {
  const [preference, setPreference] = useState<NotificationPreference | null>(null); const [attempts, setAttempts] = useState<NotificationAttempt[] | null>(null); const [error, setError] = useState('');
  const load = async () => { try { const [prefs, history] = await Promise.all([listNotificationPreferences(), listNotificationAttempts()]); setPreference(prefs[0] ?? ({id:'', user_id:'', channel:'in_app', provider:'fake', ...defaults})); setAttempts(history); } catch { setError('Unable to load notification settings. Please retry.'); } };
  useEffect(() => { void load(); }, []);
  const change = async (field: keyof typeof defaults) => { if (!preference) return; try { const next = {...preference, [field]: !preference[field]}; setPreference(await saveNotificationPreferences(next)); } catch { setError('Unable to save notification settings. Please retry.'); } };
  if (!preference || !attempts) return <section aria-label="Notification preferences"><h2>Notifications</h2>{error ? <p role="alert">{error}</p> : <p role="status">Loading notification settings...</p>}</section>;
  return <section aria-label="Notification preferences"><h2>Notifications</h2>{error && <p role="alert">{error}</p>}
    <label><input type="checkbox" checked={preference.enabled} onChange={() => void change('enabled')}/> Enable delivery</label>
    <label><input type="checkbox" checked={preference.immediate_alerts_enabled} onChange={() => void change('immediate_alerts_enabled')}/> Deliver alerts</label>
    <label><input type="checkbox" checked={preference.digest_enabled} onChange={() => void change('digest_enabled')}/> Deliver digests</label>
    <h3>Delivery history</h3>{attempts.length === 0 ? <p>No delivery attempts.</p> : <ol>{attempts.map(item => <li key={item.id}>{item.status}{item.last_error_code ? `: ${item.last_error_code}` : ''}</li>)}</ol>}
  </section>;
}
