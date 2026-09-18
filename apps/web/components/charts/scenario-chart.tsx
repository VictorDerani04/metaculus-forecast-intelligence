import { ChartHeader, type ChartMetadata } from './chart-utils';

export type ScenarioData = ChartMetadata & {
  scenarios: {name: string; weight: number; probability: number}[];
};

export function ScenarioChart({data}: {data: ScenarioData}) {
  return <section aria-label="Scenario Comparison">
    <ChartHeader title="Scenario Comparison" data={data} />
    {data.scenarios.length === 0 ? <p>No scenario outcomes available.</p> : <ul>
      {data.scenarios.map(item => <li key={item.name}>{item.name}: {item.probability}</li>)}
    </ul>}
  </section>;
}
