"use client";
import { useState, type FormEvent } from 'react';
import { saveHumanForecast, type HumanForecast } from '../lib/api';
export function ForecastEditor({questionId, current, onSaved}: {
  questionId: string; current: HumanForecast | null; onSaved: (record: HumanForecast) => void;
}) {
  const [probability, setProbability] = useState(current ? String(current.probability * 100) : '');
  const [rationale, setRationale] = useState(current?.rationale ?? '');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError('');
    try {
      const record = await saveHumanForecast(questionId, Number(probability) / 100, rationale || null);
      onSaved(record);
    } catch { setError('Failed to save human forecast'); }
    finally { setPending(false); }
  }
  return <form onSubmit={submit}>
    <label>Human probability (%)<input disabled={pending} type="number" required min="0" max="100" step="any" value={probability} onChange={event => setProbability(event.target.value)} /></label>
    <label>Rationale (optional)<textarea disabled={pending} value={rationale} onChange={event => setRationale(event.target.value)} /></label>
    {error && <p role="alert">{error}</p>}
    <button disabled={pending} type="submit">{pending ? 'Saving...' : 'Save human forecast'}</button>
  </form>;
}
