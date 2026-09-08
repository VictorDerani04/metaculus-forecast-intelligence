import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import QuestionPage from '../app/questions/[id]/page';
import type { ForecastRoomData } from '../lib/api';

const forecast = {id: 1, question_id: 'q1', user_id: 'u1', probability: 0.35, rationale: 'Human reasoning', created_at: '2026-09-07T12:00:00Z'};
const room: ForecastRoomData = {
  question: {id: 'q1', competition_id: 'cup', title: 'Forecast target', source_url: null, resolution_criteria: null, question_type: 'binary', close_at: null, resolve_at: null},
  human_forecast: forecast, history: [forecast], prior_probability: null, model_probability: null, community_probability: 0.72,
};
const candidate = {id: 'r1', question_id: 'q1', user_id: 'u1', title: 'Official release', summary: 'Output rose.', source_url: 'https://example.org/report', source_name: 'Statistics office', status: 'candidate', created_at: '2026-09-07T12:00:00Z', decisions: []};
afterEach(() => {cleanup(); vi.restoreAllMocks();});

it('shows a retryable error when initial research loading fails', async () => {
  let researchAttempts = 0;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    researchAttempts += 1;
    return researchAttempts === 1
      ? new Response('{}', {status: 500})
      : new Response(JSON.stringify({items: [], evidence: []}));
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to load research');
  fireEvent.click(screen.getByRole('button', {name: 'Retry research'}));
  expect(await screen.findByText('No candidate research yet.')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

it('protects a pending manual submission and retains its draft after failure', async () => {
  let finish!: (response: Response) => void;
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [], evidence: []}));
    return new Promise<Response>(resolve => {finish = resolve;});
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const title = await screen.findByLabelText('Research title');
  fireEvent.change(title, {target: {value: candidate.title}});
  fireEvent.change(screen.getByLabelText('Research summary'), {target: {value: candidate.summary}});
  fireEvent.change(screen.getByLabelText('Source URL'), {target: {value: candidate.source_url}});
  fireEvent.change(screen.getByLabelText('Source name'), {target: {value: candidate.source_name}});
  fireEvent.submit(title.closest('form')!);
  expect(title).toBeDisabled();
  expect(screen.getByRole('button', {name: 'Add candidate'})).toBeDisabled();
  fireEvent.submit(title.closest('form')!);
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/research-items'))).toHaveLength(1);
  await act(async () => finish(new Response('{}', {status: 500})));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to add candidate');
  expect(title).toHaveValue(candidate.title);
  expect(title).toBeEnabled();
  expect(screen.getByText('No approved evidence yet.')).toBeInTheDocument();
});

it('locks research actions until a decision finishes and prevents duplicate requests', async () => {
  let finish!: (response: Response) => void;
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [candidate], evidence: []}));
    return new Promise<Response>(resolve => {finish = resolve;});
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const approve = await screen.findByRole('button', {name: 'Approve Evidence'});
  fireEvent.click(approve);
  expect(approve).toBeDisabled();
  expect(screen.getByRole('button', {name: 'Reject'})).toBeDisabled();
  expect(screen.getByRole('button', {name: 'Add candidate'})).toBeDisabled();
  fireEvent.click(approve);
  expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/decision'))).toHaveLength(1);
  await act(async () => finish(new Response('{}', {status: 500})));
  expect(await screen.findByRole('alert')).toBeInTheDocument();
  expect(approve).toBeEnabled();
});

it('marks a candidate as a duplicate only after the user selects a related candidate', async () => {
  const original = {...candidate, id: 'r0', title: 'Earlier report'};
  let items = [original, candidate];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items, evidence: []}));
    expect(String(url)).toMatch(/\/research-items\/r1\/decision$/);
    expect(JSON.parse(String(options?.body))).toEqual({decision: 'duplicate', related_item_id: 'r0'});
    items = [original, {...candidate, status: 'duplicate'}];
    return new Response(JSON.stringify(items[1]));
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const target = (await screen.findByRole('heading', {name: 'Official release'})).closest('article')!;
  fireEvent.change(within(target).getByLabelText('Related candidate'), {target: {value: 'r0'}});
  fireEvent.click(within(target).getByRole('button', {name: 'Mark Duplicate'}));
  expect(await within(target).findByText('Status: duplicate')).toBeInTheDocument();
  expect(screen.getByText('No approved evidence yet.')).toBeInTheDocument();
});

it('shows separate empty research inbox and evidence ledger in the room', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    expect(options?.credentials).toBe('include');
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    expect(String(url)).toMatch(/\/questions\/q1\/research$/);
    return new Response(JSON.stringify({items: [], evidence: []}));
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  expect(await screen.findByRole('heading', {name: 'Research Inbox'})).toBeInTheDocument();
  expect(await screen.findByText('No candidate research yet.')).toBeInTheDocument();
  expect(within(screen.getByRole('region', {name: 'Evidence Ledger'})).getByText('No approved evidence yet.')).toBeInTheDocument();
  expect(within(screen.getByRole('group', {name: 'Human Final Forecast'})).getByText('35%')).toBeInTheDocument();
});

it('manual entry adds a candidate without approving evidence or changing forecasts', async () => {
  let items = [] as (typeof candidate)[];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items, evidence: []}));
    expect(String(url)).toMatch(/\/research-items$/);
    expect(options?.method).toBe('POST');
    expect(options?.credentials).toBe('include');
    expect(JSON.parse(String(options?.body))).toEqual({question_id: 'q1', title: 'Official release', summary: 'Output rose.', source_url: 'https://example.org/report', source_name: 'Statistics office'});
    items = [candidate];
    return new Response(JSON.stringify(candidate), {status: 201});
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const title = await screen.findByLabelText('Research title');
  fireEvent.change(title, {target: {value: candidate.title}});
  fireEvent.change(screen.getByLabelText('Research summary'), {target: {value: candidate.summary}});
  fireEvent.change(screen.getByLabelText('Source URL'), {target: {value: candidate.source_url}});
  fireEvent.change(screen.getByLabelText('Source name'), {target: {value: candidate.source_name}});
  fireEvent.click(screen.getByRole('button', {name: 'Add candidate'}));
  const inbox = within(screen.getByRole('region', {name: 'Research Inbox'}));
  expect(await inbox.findByRole('heading', {name: 'Official release'})).toBeInTheDocument();
  expect(inbox.getByText('Status: candidate')).toBeInTheDocument();
  expect(screen.getByText('No approved evidence yet.')).toBeInTheDocument();
  expect(within(screen.getByRole('group', {name: 'Human Final Forecast'})).getByText('35%')).toBeInTheDocument();
});

it('only explicit approval displays immutable provenance in the ledger and preserves the human draft', async () => {
  let approved = false;
  const entry = {...candidate, id: 'e1', research_item_id: 'r1', decision: 'approved', approved_at: '2026-09-07T13:00:00Z', dependency_evidence_ids: ['e0']};
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [{...candidate, status: approved ? 'approved' : 'candidate'}], evidence: approved ? [entry] : []}));
    expect(String(url)).toMatch(/\/research-items\/r1\/decision$/);
    expect(options?.method).toBe('POST');
    expect(options?.credentials).toBe('include');
    expect(JSON.parse(String(options?.body))).toEqual({decision: 'approved'});
    approved = true;
    return new Response(JSON.stringify({...candidate, status: 'approved'}));
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  const button = await screen.findByRole('button', {name: 'Approve Evidence'});
  expect(screen.getByText('No approved evidence yet.')).toBeInTheDocument();
  fireEvent.change(screen.getByLabelText('Human probability (%)'), {target: {value: '55'}});
  fireEvent.click(button);
  const ledger = within(screen.getByRole('region', {name: 'Evidence Ledger'}));
  expect(await ledger.findByRole('heading', {name: 'Official release'})).toBeInTheDocument();
  expect(ledger.getByRole('link', {name: 'Statistics office'})).toHaveAttribute('href', 'https://example.org/report');
  expect(ledger.getByText('Approved by u1')).toBeInTheDocument();
  expect(ledger.getByText('2026-09-07T13:00:00Z')).toBeInTheDocument();
  expect(ledger.getByText('Candidate: r1')).toBeInTheDocument();
  expect(ledger.getByText('Dependency: e0')).toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Approve Evidence'})).not.toBeInTheDocument();
  expect(screen.getByLabelText('Human probability (%)')).toHaveValue(55);
  expect(within(screen.getByRole('group', {name: 'Human Final Forecast'})).getByText('35%')).toBeInTheDocument();
  expect(within(screen.getByRole('group', {name: 'Metaculus Community Probability'})).getByText('72%')).toBeInTheDocument();
});

it.each([['Reject', 'rejected'], ['Defer', 'deferred']])('%s keeps research out of the ledger', async (label, status) => {
  let currentStatus = 'candidate';
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [{...candidate, status: currentStatus}], evidence: []}));
    expect(JSON.parse(String(options?.body))).toEqual({decision: status});
    currentStatus = status;
    return new Response(JSON.stringify({...candidate, status}));
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  fireEvent.click(await screen.findByRole('button', {name: label}));
  expect(await screen.findByText(`Status: ${status}`)).toBeInTheDocument();
  expect(screen.getByText('No approved evidence yet.')).toBeInTheDocument();
  if (status === 'rejected') expect(screen.queryByRole('button', {name: 'Approve Evidence'})).not.toBeInTheDocument();
});

it('failed approval preserves the candidate for retry and shows an error', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).endsWith('/room')) return new Response(JSON.stringify(room));
    if (String(url).endsWith('/research')) return new Response(JSON.stringify({items: [candidate], evidence: []}));
    return new Response('{}', {status: 500});
  });
  render(await QuestionPage({params: Promise.resolve({id: 'q1'})}));
  fireEvent.click(await screen.findByRole('button', {name: 'Approve Evidence'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to record research decision');
  expect(screen.getByText('Status: candidate')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Approve Evidence'})).toBeEnabled();
  expect(screen.getByText('No approved evidence yet.')).toBeInTheDocument();
});
