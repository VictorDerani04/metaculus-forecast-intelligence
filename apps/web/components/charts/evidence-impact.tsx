import { ChartHeader, type ChartMetadata } from './chart-utils';

export type EvidenceImpactData = ChartMetadata & {
  evidence: {evidence_id: string; title: string; summary: string; dependency_warning: boolean}[];
};

export function EvidenceImpactChart({data}: {data: EvidenceImpactData}) {
  return <section aria-label="Evidence Impact">
    <ChartHeader title="Evidence Impact" data={data} />
    {data.evidence.length === 0 ? <p>No linked approved evidence.</p> : <ul>
      {data.evidence.map(item => <li key={item.evidence_id}>{item.title}{item.dependency_warning ? ' · dependency warning' : ''}</li>)}
    </ul>}
  </section>;
}
