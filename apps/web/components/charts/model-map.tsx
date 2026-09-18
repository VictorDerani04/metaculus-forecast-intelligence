import { ChartHeader, type ChartMetadata } from './chart-utils';

export type ModelMapData = ChartMetadata & {
  nodes: {id: string; kind: string; label: string}[];
  edges: {source: string; target: string; relationship: string}[];
};

export function ModelMapChart({data}: {data: ModelMapData}) {
  return <section aria-label="Causal Model Map">
    <ChartHeader title="Causal Model Map" data={data} />
    {data.nodes.length === 0 ? <p>No model map nodes available.</p> : <ul>
      {data.nodes.map(node => <li key={node.id}>{node.kind}: {node.label}</li>)}
    </ul>}
    <p>{data.edges.length} relationships</p>
  </section>;
}
