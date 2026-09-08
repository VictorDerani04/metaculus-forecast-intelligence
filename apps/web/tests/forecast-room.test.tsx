import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import QuestionPage from '../app/questions/[id]/page';

const room = {
  question: {
    id: 'q1', competition_id: 'cup', title: 'Will event X occur?',
    source_url: 'https://www.metaculus.com/questions/45262/',
    resolution_criteria: 'Official results determine resolution.',
    question_type: 'binary', close_at: '2026-11-01T00:00:00Z', resolve_at: null,
  },
  prior_probability: null, model_probability: null, human_forecast: null,
  community_probability: 0.72, history: [],
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('loads the question room and displays four distinct probability concepts', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [], evidence: []}));
    expect(String(url)).toMatch(/\/questions\/q1\/room$/);
    expect(options?.credentials).toBe('include');
    return new Response(JSON.stringify(room), {status: 200});
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  expect(await screen.findByRole('heading', {name: 'Will event X occur?'})).toBeInTheDocument();
  expect(screen.getByText('Official results determine resolution.')).toBeInTheDocument();
  for (const label of ['Prior/Base Rate', 'Model Probability', 'Human Final Forecast']) {
    expect(within(screen.getByRole('group', {name: label})).getByText('Unavailable')).toBeInTheDocument();
  }
  expect(within(screen.getByRole('group', {name: 'Metaculus Community Probability'})).getByText('72%')).toBeInTheDocument();
  expect(screen.getByText('No human forecasts recorded yet.')).toBeInTheDocument();
});

it('explicit saves append human history and preserve community probability', async () => {
  let sequence = 0;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [], evidence: []}));
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    expect(String(url)).toMatch(/\/questions\/q1\/forecasts$/);
    expect(options?.method).toBe('POST');
    expect(options?.credentials).toBe('include');
    const payload = JSON.parse(String(options?.body));
    return new Response(JSON.stringify({id: ++sequence, question_id: 'q1', user_id: 'u1',
      ...payload, created_at: `2026-09-07T12:0${sequence}:00Z`}), {status: 201});
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const input = await screen.findByLabelText('Human probability (%)');
  expect(input).toHaveValue(null);
  const {fireEvent} = await import('@testing-library/react');
  fireEvent.change(input, {target: {value: '35'}});
  fireEvent.change(screen.getByLabelText('Rationale (optional)'), {target: {value: 'First assessment'}});
  fireEvent.click(screen.getByRole('button', {name: 'Save human forecast'}));
  expect(await within(screen.getByRole('group', {name: 'Human Final Forecast'})).findByText('35%')).toBeInTheDocument();
  fireEvent.change(input, {target: {value: '60'}});
  fireEvent.change(screen.getByLabelText('Rationale (optional)'), {target: {value: 'Updated assessment'}});
  fireEvent.click(screen.getByRole('button', {name: 'Save human forecast'}));
  expect(await within(screen.getByRole('group', {name: 'Human Final Forecast'})).findByText('60%')).toBeInTheDocument();
  const history = within(screen.getByRole('region', {name: 'Human forecast history'}));
  expect(history.getAllByRole('listitem')).toHaveLength(2);
  expect(history.getByText('First assessment')).toBeInTheDocument();
  expect(history.getByText('Updated assessment')).toBeInTheDocument();
  expect(history.getAllByRole('listitem')[0]).toHaveTextContent('35%');
  expect(history.getAllByRole('listitem')[1]).toHaveTextContent('60%');
  expect(within(screen.getByRole('group', {name: 'Metaculus Community Probability'})).getByText('72%')).toBeInTheDocument();
});

it('failed saves retain the draft and saved human history', async () => {
  const saved = {id: 1, question_id: 'q1', user_id: 'u1', probability: 0.2, rationale: 'Saved reasoning', created_at: '2026-09-07T12:00:00Z'};
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => String(url).endsWith('/research') ? new Response(JSON.stringify({items: [], evidence: []})) : String(url).endsWith('/room')
    ? new Response(JSON.stringify({...room, human_forecast: saved, history: [saved]}))
    : new Response('{}', {status: 500}));
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const input = await screen.findByLabelText('Human probability (%)');
  expect(input).toHaveValue(20);
  const {fireEvent} = await import('@testing-library/react');
  fireEvent.change(input, {target: {value: '55'}});
  fireEvent.click(screen.getByRole('button', {name: 'Save human forecast'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to save human forecast');
  expect(input).toHaveValue(55);
  expect(within(screen.getByRole('group', {name: 'Human Final Forecast'})).getByText('20%')).toBeInTheDocument();
  expect(screen.getAllByRole('listitem')).toHaveLength(1);
});

it('prevents duplicate saves while a request is pending', async () => {
  let finish!: (response: Response) => void;
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => String(url).endsWith('/research') ? new Response(JSON.stringify({items: [], evidence: []})) : String(url).endsWith('/room')
    ? new Response(JSON.stringify(room)) : new Promise<Response>(resolve => {finish = resolve;}));
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const input = await screen.findByLabelText('Human probability (%)');
  const {fireEvent, act} = await import('@testing-library/react');
  fireEvent.change(input, {target: {value: '0'}});
  fireEvent.click(screen.getByRole('button', {name: 'Save human forecast'}));
  expect(screen.getByRole('button', {name: 'Saving...'})).toBeDisabled();
  expect(input).toBeDisabled();
  fireEvent.submit(input.closest('form')!);
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/forecasts'))).toHaveLength(1);
  await act(async () => finish(new Response(JSON.stringify({id: 1, question_id: 'q1', user_id: 'u1', probability: 0, rationale: null, created_at: '2026-09-07T12:00:00Z'}), {status: 201})));
  expect(within(screen.getByRole('group', {name: 'Human Final Forecast'})).getByText('0%')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Save human forecast'})).toBeEnabled();
});

it('shows room load failures without an editable forecast', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', {status: 404}));
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to load forecast room');
  expect(screen.queryByLabelText('Human probability (%)')).not.toBeInTheDocument();
});

it('external estimate changes never overwrite the human draft or saved value', async () => {
  const {ForecastEditor} = await import('../components/forecast-editor');
  const {ProbabilityStrip} = await import('../components/probability-strip');
  const {fireEvent} = await import('@testing-library/react');
  const saved = {id: 1, question_id: 'q1', user_id: 'u1', probability: 0.4, rationale: null, created_at: '2026-09-07T12:00:00Z'};
  const onSaved = vi.fn();
  const view = (community: number | null, model: number | null) => <>
    <ProbabilityStrip room={{...room, human_forecast: saved, community_probability: community, model_probability: model}} />
    <ForecastEditor questionId="q1" current={saved} onSaved={onSaved} />
  </>;
  const {rerender} = render(view(null, null));
  fireEvent.change(screen.getByLabelText('Human probability (%)'), {target: {value: '55'}});
  rerender(view(0, 0.9));
  expect(screen.getByLabelText('Human probability (%)')).toHaveValue(55);
  expect(within(screen.getByRole('group', {name: 'Human Final Forecast'})).getByText('40%')).toBeInTheDocument();
  expect(within(screen.getByRole('group', {name: 'Metaculus Community Probability'})).getByText('0%')).toBeInTheDocument();
  expect(within(screen.getByRole('group', {name: 'Model Probability'})).getByText('90%')).toBeInTheDocument();
  expect(onSaved).not.toHaveBeenCalled();
});
