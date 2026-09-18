import type {AttentionItem} from '../lib/api';

export function PriorityExplanation({item}: {item: AttentionItem}) {
  return <details>
    <summary><button type="button">Why?</button></summary>
    <ul>{item.priority.reasons.length
      ? item.priority.reasons.map(reason => <li key={reason}>{reason}</li>)
      : <li>No priority signals are currently available.</li>}</ul>
    <ul aria-label="Priority contributions">
      {item.priority.components.map(component =>
        <li key={component.name}>{component.name.replaceAll('_', ' ')}: {component.contribution.toFixed(1)}</li>)}
    </ul>
  </details>;
}
