import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { QuestionTable } from '../components/question-table';

afterEach(() => cleanup());

it('sorts attention questions by priority and explains the top question', () => {
  render(<QuestionTable questions={[
    {question_id: 'q1', title: 'Lower priority', competition_id: 'c1',
      priority: {score: 20, components: [], reasons: ['Forecast is stale']},
      human_probability: null, model_probability: null, crowd_probability: null, resolve_at: null},
    {question_id: 'q2', title: 'Needs review', competition_id: 'c1',
      priority: {score: 80, components: [], reasons: ['No initial human forecast']},
      human_probability: null, model_probability: 0.7, crowd_probability: null, resolve_at: null},
  ]} />);

  const links = screen.getAllByRole('link');
  expect(links[0]).toHaveTextContent('Needs review');
  expect(screen.getByText('No initial human forecast')).toBeInTheDocument();
  expect(screen.getAllByRole('button', {name: 'Why?'})).toHaveLength(2);
});
