import { ChartHeader, type ChartMetadata } from './chart-utils';

export type SensitivityData = ChartMetadata & {
  impacts: {name: string; baseline: number; downside: number; upside: number; impact: number}[];
};

export function SensitivityChart({data}: {data: SensitivityData}) {
  return <section aria-label="Sensitivity and Tornado Analysis">
    <ChartHeader title="Sensitivity / Tornado" data={data} />
    {data.impacts.length === 0 ? <p>No sensitivity analysis available.</p> : <ul>
      {data.impacts.map(item => <li key={item.name}>{item.name}: impact {item.impact}</li>)}
    </ul>}
  </section>;
}
