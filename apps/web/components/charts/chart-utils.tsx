export type ChartMetadata = {
  model_version: number | null;
  generated_at: string;
  why_this_chart: string;
};

export function ChartHeader({title, data}: {title: string; data: ChartMetadata}) {
  return <header>
    <h2>{title}</h2>
    <p><strong>Why this chart?</strong> {data.why_this_chart}</p>
    <p><span>Model version {data.model_version ?? 'unavailable'}</span> · Generated {data.generated_at}</p>
  </header>;
}
