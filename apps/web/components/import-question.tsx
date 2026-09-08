"use client";

import { type FormEvent, useState } from 'react';
import { importQuestion, ImportError, type ImportedQuestion } from '../lib/api';

export function ImportQuestion({competitionId, onImported}: {competitionId: string; onImported?: () => void}) {
  const [url, setUrl] = useState('');
  const [question, setQuestion] = useState<ImportedQuestion | null>(null);
  const [manual, setManual] = useState(false);
  const [title, setTitle] = useState('');
  const [criteria, setCriteria] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setPending(true);
    setError('');
    try {
      setQuestion(await importQuestion(competitionId, url, manual ? {
        title, resolution_criteria: criteria,
      } : undefined));
      setManual(false);
      onImported?.();
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Import failed');
      if (failure instanceof ImportError && failure.code === 'manual_entry_required') setManual(true);
    } finally {
      setPending(false);
    }
  }

  return <section aria-label="Import Metaculus question">
    <form onSubmit={submit}>
      <label>Metaculus question URL
        <input disabled={pending} type="url" required value={url} onChange={event => {
          setUrl(event.target.value);
          setManual(false);
          setTitle('');
          setCriteria('');
          setError('');
        }} />
      </label>
      {manual && <>
        <label>Question title<input required maxLength={500} value={title} onChange={event => setTitle(event.target.value)} /></label>
        <label>Resolution criteria<textarea value={criteria} onChange={event => setCriteria(event.target.value)} /></label>
      </>}
      <button disabled={pending} type="submit">{pending ? 'Importing...' : manual ? 'Save manual question' : 'Import question'}</button>
    </form>
    {error && <p role="alert">{error}</p>}
    {question && <article>
      <h3>{question.title}</h3>
      <a href={`/questions/${encodeURIComponent(question.id)}`}>Open Forecast Room</a>
      <a href={question.source_url}>View on Metaculus</a>
      {question.import_status === 'partial' && <p>Some source details are unavailable.</p>}
      {question.import_status === 'manual' && <p>Saved from manual entry.</p>}
      <p>{question.resolution_criteria ?? 'Resolution criteria unavailable'}</p>
      <p>Type: {question.question_type ?? 'unavailable'}</p>
      <p>Closes: {question.close_at ?? 'unavailable'}</p>
      <p>Resolves: {question.resolve_at ?? 'unavailable'}</p>
      <p>{question.crowd_probability === null ? 'Community prediction unavailable' : `Community prediction: ${question.crowd_probability * 100}%`}</p>
    </article>}
  </section>;
}
