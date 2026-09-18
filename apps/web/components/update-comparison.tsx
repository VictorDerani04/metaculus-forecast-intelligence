import type {DecisionRecord} from '../lib/api';

export function UpdateComparison({current, previous}: {current: DecisionRecord; previous?: DecisionRecord}) {
  return <section aria-label="Decision comparison">
    <h3>What changed</h3>
    <p>Human forecast: {previous?.human_probability == null ? '—' : `${previous.human_probability * 100}%`} → {current.human_probability == null ? '—' : `${current.human_probability * 100}%`}</p>
    <p>Model: {previous?.model_probability == null ? '—' : `${previous.model_probability * 100}%`} → {current.model_probability == null ? '—' : `${current.model_probability * 100}%`}</p>
  </section>;
}
