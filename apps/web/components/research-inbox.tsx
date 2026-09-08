"use client";
import { useEffect, useState } from 'react';
import { getResearch, addResearchCandidate, decideResearch, type ResearchData, type ResearchDecisionInput } from '../lib/api';
import { EvidenceLedger } from './evidence-ledger';
export function ResearchInbox({questionId}: {questionId: string}) {
  const [data, setData] = useState<ResearchData | null>(null);
  const [title, setTitle] = useState('');
  const [summary, setSummary] = useState('');
  const [sourceUrl, setSourceUrl] = useState('');
  const [sourceName, setSourceName] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const [relatedItemIds, setRelatedItemIds] = useState<Record<string, string>>({});
  useEffect(() => {
    let active = true;
    getResearch(questionId)
      .then(value => {if (active) setData(value);})
      .catch(() => {if (active) setError('Failed to load research');});
    return () => {active = false;};
  }, [questionId]);
  async function retryResearch() {
    setError('');
    try { setData(await getResearch(questionId)); }
    catch { setError('Failed to load research'); }
  }
  async function recordDecision(itemId: string, payload: ResearchDecisionInput) {
    if (pending) return;
    setPending(true);
    setError('');
    try {
      await decideResearch(itemId, payload);
      setData(await getResearch(questionId));
    } catch { setError('Failed to record research decision'); }
    finally { setPending(false); }
  }
  return <>
    <section aria-label="Research Inbox"><h2>Research Inbox</h2>
      {error && <p role="alert">{error}</p>}
      {!data && error && <button type="button" onClick={retryResearch}>Retry research</button>}
      {data ? <>
        <form onSubmit={async event => {
          event.preventDefault();
          if (pending) return;
          setPending(true);
          setError('');
          try {
            const item = await addResearchCandidate({question_id: questionId, title, summary, source_url: sourceUrl, source_name: sourceName});
            setData(current => current && ({...current, items: [...current.items, item]}));
            setTitle(''); setSummary(''); setSourceUrl(''); setSourceName('');
          } catch { setError('Failed to add candidate'); }
          finally { setPending(false); }
        }}>
          <label>Research title<input disabled={pending} required maxLength={500} value={title} onChange={event => setTitle(event.target.value)} /></label>
          <label>Research summary<textarea disabled={pending} required value={summary} onChange={event => setSummary(event.target.value)} /></label>
          <label>Source URL<input disabled={pending} required type="url" value={sourceUrl} onChange={event => setSourceUrl(event.target.value)} /></label>
          <label>Source name<input disabled={pending} required maxLength={255} value={sourceName} onChange={event => setSourceName(event.target.value)} /></label>
          <button disabled={pending} type="submit">Add candidate</button>
        </form>
        {data.items.length === 0 && <p>No candidate research yet.</p>}
        {data.items.map(item => <article key={item.id}>
          <h3>{item.title}</h3><p>{item.summary}</p>
          <a href={item.source_url}>{item.source_name}</a>
          <p>Status: {item.status}</p>
                    {(item.status === 'candidate' || item.status === 'deferred') && <>
            {([['approved', 'Approve Evidence'], ['rejected', 'Reject'], ['deferred', 'Defer']] as const).map(([decision, label]) =>
              <button disabled={pending} key={decision} type="button" onClick={() => recordDecision(item.id, {decision})}>{label}</button>)}
            {data.items.some(other => other.id !== item.id) && <>
              <label>Related candidate<select disabled={pending} value={relatedItemIds[item.id] ?? ''} onChange={event => setRelatedItemIds(current => ({...current, [item.id]: event.target.value}))}>
                <option value="">Select candidate</option>
                {data.items.filter(other => other.id !== item.id).map(other => <option key={other.id} value={other.id}>{other.title}</option>)}
              </select></label>
              <button disabled={pending || !relatedItemIds[item.id]} type="button" onClick={() => recordDecision(item.id, {decision: 'duplicate', related_item_id: relatedItemIds[item.id]})}>Mark Duplicate</button>
              <button disabled={pending || !relatedItemIds[item.id]} type="button" onClick={() => recordDecision(item.id, {decision: 'superseded', related_item_id: relatedItemIds[item.id]})}>Mark Superseded</button>
            </>}
          </>}
        </article>)}
      </> : !error && <p>Loading research...</p>}
    </section>
    <EvidenceLedger entries={data?.evidence ?? []} />
  </>;
}
