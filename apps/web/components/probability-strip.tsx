import { type ForecastRoomData } from '../lib/api';
export function ProbabilityStrip({room}: {room: ForecastRoomData}) {
  const values = [
    ['Prior/Base Rate', room.prior_probability], ['Model Probability', room.model_probability],
    ['Human Final Forecast', room.human_forecast?.probability ?? null],
    ['Metaculus Community Probability', room.community_probability],
  ] as const;
  return <section aria-label="Probability estimates">{values.map(([label, value]) =>
    <fieldset key={label}><legend>{label}</legend><p>{value === null ? 'Unavailable' : `${Number((value * 100).toFixed(6))}%`}</p></fieldset>
  )}</section>;
}
