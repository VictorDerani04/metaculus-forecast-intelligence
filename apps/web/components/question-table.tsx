import type {AttentionItem} from '../lib/api';
import {PriorityExplanation} from './priority-explanation';

export function QuestionTable({questions}: {questions: AttentionItem[]}) {
  const sorted = [...questions].sort((left, right) =>
    right.priority.score - left.priority.score || left.question_id.localeCompare(right.question_id));
  return <section aria-label="Attention priorities">
    <h2>Attention priorities</h2>
    {sorted.length === 0 ? <p>No questions need attention.</p> : <ol>
      {sorted.map(item => <li key={item.question_id}>
        <a href={`/questions/${encodeURIComponent(item.question_id)}`}>{item.title}</a>
        <p>Priority: {item.priority.score}</p>
        <p>Human: {item.human_probability ?? 'Not forecast'}; Model: {item.model_probability ?? 'Not available'}; Crowd: {item.crowd_probability ?? 'Not available'}</p>
        <p>Resolves: {item.resolve_at ? new Date(item.resolve_at).toLocaleDateString() : 'No deadline'}</p>
        <PriorityExplanation item={item} />
      </li>)}
    </ol>}
  </section>;
}
