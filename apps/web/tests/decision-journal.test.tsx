import {render, screen} from '@testing-library/react';
import {expect, it, vi} from 'vitest';
import {DecisionJournal} from '../components/decision-journal';

it('renders a decision snapshot and historical entries without mutating forecasts', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).endsWith('/audit')) {
      return new Response('[]', {status: 200});
    }
    return new Response(JSON.stringify([{
      id: 'd1', question_id: 'q1', competition_id: 'c1', user_id: 'u1',
      human_probability: 0.64, rationale: 'Evidence supports this.',
      prior_probability: null, model_probability: 0.58, crowd_probability: 0.51,
      evidence_ids: ['e1'], model_spec_id: 'm1', model_run_id: 'r1',
      created_at: '2026-09-17T20:00:00Z',
    }]), {status: 200});
  });

  render(<DecisionJournal questionId="q1" />);

  expect(await screen.findByText('Evidence supports this.')).toBeInTheDocument();
  expect(screen.getByText(/Human: 64%/)).toBeInTheDocument();
  expect(screen.getByText(/Model: 58%/)).toBeInTheDocument();
  expect(screen.getByText(/Crowd: 51%/)).toBeInTheDocument();
  expect(globalThis.fetch).toHaveBeenCalledTimes(2);
});
