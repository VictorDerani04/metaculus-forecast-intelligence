import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CopilotChat } from '../components/copilot-chat';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('provides a forecast-scoped message input and send action', () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(
    new Response(JSON.stringify({messages: []}), {status: 200}),
  );
  render(<CopilotChat questionId="q1" />);
  expect(screen.getByRole('heading', {name: 'Copilot'})).toBeInTheDocument();
  expect(screen.getByLabelText('Copilot message')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Send message'})).toBeInTheDocument();
});

it('renders a successful exchange and clears the draft', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    if (String(url).endsWith('/chat') && !options?.method) {
      return new Response(JSON.stringify({messages: []}), {status: 200});
    }
    return new Response(JSON.stringify({
      user_message: {id: 1, role: 'user', content: 'What matters?', created_at: '2026-01-01T00:00:00Z'},
      assistant_message: {id: 2, role: 'assistant', content: 'Approved evidence matters.', created_at: '2026-01-01T00:00:01Z'},
      proposed_actions: [],
    }), {status: 201});
  });
  render(<CopilotChat questionId="q1" />);
  const input = await screen.findByLabelText('Copilot message');
  fireEvent.change(input, {target: {value: 'What matters?'}});
  fireEvent.click(screen.getByRole('button', {name: 'Send message'}));
  expect(await screen.findByText('Approved evidence matters.')).toBeInTheDocument();
  expect(input).toHaveValue('');
});

it('keeps a failed draft and prevents duplicate submission while pending', async () => {
  let finish!: (response: Response) => void;
  const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async url =>
    String(url).endsWith('/chat')
      ? new Promise<Response>(resolve => { finish = resolve; })
      : new Response(JSON.stringify({messages: []}), {status: 200}),
  );
  render(<CopilotChat questionId="q1" />);
  const input = await screen.findByLabelText('Copilot message');
  fireEvent.change(input, {target: {value: 'Retry me'}});
  fireEvent.click(screen.getByRole('button', {name: 'Send message'}));
  expect(screen.getByRole('button', {name: 'Sending...'})).toBeDisabled();
  fireEvent.submit(input.closest('form')!);
  expect(fetchMock.mock.calls.filter(([url, options]) =>
    String(url).endsWith('/chat') && options?.method === 'POST',
  )).toHaveLength(1);
  finish(new Response('{}', {status: 503}));
  await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('unavailable'));
  expect(input).toHaveValue('Retry me');
});
