import { ChartHeader, type ChartMetadata } from './chart-utils';

export type DistributionData = ChartMetadata & {
  available: boolean;
  probability: number | null;
  values: number[];
  unavailable_reason: string | null;
};

export function DistributionChart({data}: {data: DistributionData}) {
  return <section aria-label="Probability Distribution">
    <ChartHeader title="Probability Distribution" data={data} />
    {data.available
      ? <p>Central probability: {data.probability ?? 'unavailable'}</p>
      : <><p>Distribution unavailable</p>{data.unavailable_reason && <p>{data.unavailable_reason}</p>}</>}
  </section>;
}
