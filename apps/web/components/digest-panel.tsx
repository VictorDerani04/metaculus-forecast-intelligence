"use client";
import {useEffect, useState} from 'react';
import {getDigest, listDigests, type DigestDetail, type DigestSummary} from '../lib/api';
export function DigestPanel() {
  const [digests, setDigests] = useState<DigestSummary[] | null>(null); const [selected, setSelected] = useState<DigestDetail | null>(null); const [error, setError] = useState('');
  useEffect(() => { listDigests().then(async value => { setDigests(value); if (value[0]) setSelected(await getDigest(value[0].id)); }).catch(() => setError('Unable to load digests. Please retry.')); }, []);
  if (!digests) return <section aria-label="Digests"><h2>Digests</h2>{error ? <p role="alert">{error}</p> : <p role="status">Loading digests...</p>}</section>;
  return <section aria-label="Digests"><h2>Digests</h2>{error && <p role="alert">{error}</p>}{digests.length === 0 ? <p>No digests yet.</p> : <><p>{selected?.period_start} – {selected?.period_end}</p><p>Generated: {selected?.generated_at}</p><ol>{selected?.items.map(item => <li key={item.id}><h3>{item.finding.title}</h3><p>{item.finding.summary}</p></li>)}</ol></>}</section>;
}
