import type { Evidence } from '../lib/api';
export function EvidenceLedger({entries}: {entries: Evidence[]}) {
  return <section aria-label="Evidence Ledger"><h2>Evidence Ledger</h2>
    {entries.length === 0 ? <p>No approved evidence yet.</p> : entries.map(entry => <article key={entry.id} id={`evidence-${entry.id}`}>
      <h3>{entry.title}</h3><p>{entry.summary}</p>
      <a href={entry.source_url}>{entry.source_name}</a>
      <p>Approved by {entry.user_id}</p>
      <time dateTime={entry.approved_at}>{entry.approved_at}</time>
      <p>Candidate: {entry.research_item_id}</p>
      {entry.dependency_evidence_ids.map(id => <p key={id}>Dependency: {id}</p>)}
    </article>)}
  </section>;
}
