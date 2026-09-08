import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CompetitionDashboard } from '../app/competitions/page';
afterEach(() => {cleanup(); vi.restoreAllMocks();});
it('opens saved question rooms from their competition', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    expect(String(url)).toMatch(/\/competitions\/cup\/questions$/);
    expect(options?.credentials).toBe('include');
    return new Response(JSON.stringify([{id: 'q1', competition_id: 'cup', title: 'Saved question'}]));
  });
  render(<CompetitionDashboard competitions={[{id: 'cup', name: 'Cup', questionCount: 1}]} />);
  fireEvent.click(screen.getByRole('button', {name: 'View questions'}));
  expect(await screen.findByRole('link', {name: 'Saved question'})).toHaveAttribute('href', '/questions/q1');
});
it('shows a load error and allows retrying the question list', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response('{}', {status: 500}))
    .mockResolvedValueOnce(new Response('[]'));
  render(<CompetitionDashboard competitions={[{id: 'cup', name: 'Cup', questionCount: 0}]} />);
  fireEvent.click(screen.getByRole('button', {name: 'View questions'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Failed to load questions');
  fireEvent.click(screen.getByRole('button', {name: 'View questions'}));
  expect(await screen.findByText('No questions saved yet.')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
