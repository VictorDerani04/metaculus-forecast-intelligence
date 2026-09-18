"use client";
import {useEffect, useState, type FormEvent} from 'react';
import {listAuditEvents, listDecisions, recordDecision, type AuditEvent, type DecisionRecord} from '../lib/api';
import {UpdateComparison} from './update-comparison';

function percent(value: number | null) {
  return value == null ? 'Unavailable' : `${Number((value * 100).toFixed(4))}%`;
}

export function DecisionJournal({questionId, autoLoad = true}: {questionId: string; autoLoad?: boolean}) {
  const [decisions, setDecisions] = useState<DecisionRecord[] | null>(null);
  const [audit, setAudit] = useState<AuditEvent[] | null>(null);
  const [rationale, setRationale] = useState('');
  const [error, setError] = useState('');
  function load() {
    setError('');
    Promise.all([listDecisions(questionId), listAuditEvents(questionId)])
      .then(([journal, events]) => {setDecisions(journal); setAudit(events);})
      .catch(() => setError('Failed to load decision history'));
  }
  useEffect(() => { if (autoLoad) load(); }, [questionId, autoLoad]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    try {
      const decision = await recordDecision(questionId, rationale);
      setDecisions(current => [...(current ?? []), decision]);
      setRationale('');
    } catch { setError('Failed to record decision'); }
  }
  if (error) return <section aria-label="Decision Journal"><p role="status">{error}</p><button type="button" onClick={load}>Retry decision history</button></section>;
  if (!decisions || !audit) return <section aria-label="Decision Journal">
    {!autoLoad && <button type="button" onClick={load}>Load decision history</button>}
    {autoLoad && <p role="status">Loading decision history...</p>}
  </section>;
  const latest = decisions[decisions.length - 1];
  return <section aria-label="Decision Journal">
    <h2>Decision Journal</h2>
    <form onSubmit={submit}>
      <label>Decision rationale<textarea required value={rationale} onChange={event => setRationale(event.target.value)} /></label>
      <button type="submit">Record decision</button>
    </form>
    {decisions.length === 0 ? <p>No decisions recorded yet.</p> : <ol>
      {decisions.map((decision, index) => <li key={decision.id}>
        <p>{decision.rationale}</p>
        <p>Human: {percent(decision.human_probability)}; Model: {percent(decision.model_probability)}; Crowd: {percent(decision.crowd_probability)}</p>
        <time dateTime={decision.created_at}>{decision.created_at}</time>
        {index > 0 && <UpdateComparison current={decision} previous={decisions[index - 1]} />}
      </li>)}
    </ol>}
    <section aria-label="Audit history"><h3>Activity history</h3>
      {audit.length === 0 ? <p>No activity recorded yet.</p> : <ol>{audit.map(event =>
        <li key={event.id}>{event.action} <time dateTime={event.created_at}>{event.created_at}</time></li>)}</ol>}
    </section>
    {latest && <p>Latest decision is an immutable snapshot.</p>}
  </section>;
}
