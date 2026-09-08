import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import CompetitionsPage from '../app/competitions/page';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('imports from the competition dashboard and updates its question count', async () => {
  const {fireEvent} = await import('@testing-library/react');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (String(url).endsWith('/questions/import')) return new Response(JSON.stringify({
      id: 'q1', competition_id: 'cup', title: 'New imported question',
      source_url: 'https://www.metaculus.com/questions/45262/',
      source_post_id: 45262, resolution_criteria: null, question_type: null,
      close_at: null, resolve_at: null, crowd_probability: null, import_status: 'partial',
    }), {status: 201});
    return new Response(JSON.stringify([{id: 'cup', name: 'Cup', question_count: 0}]), {status: 200});
  });
  render(<CompetitionsPage />);
  await screen.findByRole('heading', {name: 'Cup'});
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: 'https://www.metaculus.com/questions/45262/'}});
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  expect(await screen.findByText('New imported question')).toBeInTheDocument();
  expect(screen.getByText('1 question')).toBeInTheDocument();
});


it('lets an empty account create a competition so it can import a question', async () => {
  const {fireEvent} = await import('@testing-library/react');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) => {
    if (options?.method === 'POST') {
      expect(JSON.parse(String(options.body))).toEqual({name: 'Fall Cup'});
      return new Response(JSON.stringify({id: 'new-cup', name: 'Fall Cup', question_count: 0}), {status: 201});
    }
    return new Response('[]', {status: 200});
  });
  render(<CompetitionsPage />);
  fireEvent.change(screen.getByLabelText('Competition name'), {target: {value: 'Fall Cup'}});
  fireEvent.click(screen.getByRole('button', {name: 'Create competition'}));
  expect(await screen.findByRole('heading', {name: 'Fall Cup'})).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Import question'})).toBeInTheDocument();
});

it('shows creation failure and keeps the entered competition name for retry', async () => {
  const {fireEvent} = await import('@testing-library/react');
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) =>
    options?.method === 'POST' ? new Response('{}', {status: 500}) : new Response('[]', {status: 200}));
  render(<CompetitionsPage />);
  fireEvent.change(screen.getByLabelText('Competition name'), {target: {value: 'Fall Cup'}});
  fireEvent.click(screen.getByRole('button', {name: 'Create competition'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to create competition');
  expect(screen.getByLabelText('Competition name')).toHaveValue('Fall Cup');
});
