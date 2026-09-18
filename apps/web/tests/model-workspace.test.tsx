import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ModelWorkspace } from '../components/model-workspace';
import type { ModelSpec } from '../lib/api';

const draft: ModelSpec = {
  id: 'm1', user_id: 'u1', question_id: 'q1', family: 'base_rate', rationale: 'Reference class',
  parameters: {probability: 0.42}, assumptions: [], evidence_ids: ['e1'], source_model_id: null,
  status: 'draft', version: 1, approved_at: null, created_at: '2026-09-15T12:00:00Z',
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('shows model status, provenance, and only explicit approval/run controls', async () => {
  let models = [draft];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/questions/q1/models')) return new Response(JSON.stringify(models));
    expect(options?.method).toBe('POST');
    expect(String(url)).toMatch(/\/models\/m1\/activate$/);
    models = [{...draft, status: 'approved', approved_at: '2026-09-15T12:01:00Z'}];
    return new Response(JSON.stringify(models[0]));
  });
  render(<ModelWorkspace questionId="q1" onRun={vi.fn()} />);
  const workspace = await screen.findByRole('region', {name: 'Model Workspace'});
  expect(within(workspace).getByText('Draft model')).toBeInTheDocument();
  expect(within(workspace).getByText('Evidence: e1')).toBeInTheDocument();
  fireEvent.click(within(workspace).getByRole('button', {name: 'Approve Model'}));
  expect(await within(workspace).findByText('Approved model')).toBeInTheDocument();
  expect(within(workspace).getByRole('button', {name: 'Run Model'})).toBeInTheDocument();
});

it('locks a pending run, preserves retryable errors, and updates Model Probability only after success', async () => {
  const onRun = vi.fn();
  let finish!: (response: Response) => void;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async url => {
    if (String(url).endsWith('/questions/q1/models')) return new Response(JSON.stringify([{...draft, status: 'approved', approved_at: '2026-09-15T12:01:00Z'}]));
    return new Promise<Response>(resolve => { finish = resolve; });
  });
  render(<ModelWorkspace questionId="q1" onRun={onRun} />);
  const run = await screen.findByRole('button', {name: 'Run Model'});
  fireEvent.click(run);
  expect(screen.getByRole('button', {name: 'Running...'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button', {name: 'Running...'}));
  await act(async () => finish(new Response('{}', {status: 422})));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to run model');
  expect(screen.getByRole('button', {name: 'Run Model'})).toBeEnabled();
  expect(onRun).not.toHaveBeenCalled();
});
