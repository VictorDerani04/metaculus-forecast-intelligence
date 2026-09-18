import { ChartHeader, type ChartMetadata } from './chart-utils';

export type ProbabilityHistoryData = ChartMetadata & {
  human: {timestamp: string; probability: number}[];
  model: {timestamp: string; probability: number}[];
  crowd: {timestamp: string; probability: number}[];
};

export function ProbabilityHistoryChart({data}: {data: ProbabilityHistoryData}) {
  return <section aria-label="Probability History">
    <ChartHeader title="Probability History" data={data} />
    <ul>
      <li>Human Final Forecast: {data.human.length} observations</li>
      <li>Model Probability: {data.model.length} observations</li>
      <li>Metaculus Community Probability: {data.crowd.length} observations</li>
    </ul>
  </section>;
}
