import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ImportQuestion } from '../components/import-question';

const imported = {
  id: 'q1', competition_id: 'cup', title: 'Imported question',
  source_post_id: 45262, source_url: 'https://www.metaculus.com/questions/45262/',
  resolution_criteria: 'Official results.', question_type: 'binary',
  close_at: '2026-11-01T00:00:00Z', resolve_at: null,
  crowd_probability: null, import_status: 'partial',
};

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('imports a question into the selected competition and shows source details', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, options) => {
    expect(String(url)).toMatch(/\/competitions\/cup\/questions\/import$/);
    expect(options?.credentials).toBe('include');
    expect(JSON.parse(String(options?.body))).toEqual({url: 'https://www.metaculus.com/questions/45262/'});
    return new Response(JSON.stringify(imported), {status: 201});
  });
  render(<ImportQuestion competitionId="cup" />);
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: imported.source_url}});
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  expect(await screen.findByText('Imported question')).toBeInTheDocument();
  expect(screen.getByText('Community prediction unavailable')).toBeInTheDocument();
  expect(screen.getByText('Some source details are unavailable.')).toBeInTheDocument();
  expect(screen.getByText('Official results.')).toBeInTheDocument();
  expect(screen.getByRole('link', {name: 'Open Forecast Room'})).toHaveAttribute('href', '/questions/q1');
});

it('offers manual entry when live import is unavailable and saves the entered details', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) => {
    const body = JSON.parse(String(options?.body));
    if (!body.manual_details) return new Response(JSON.stringify({detail: {
      code: 'manual_entry_required', message: 'Live import unavailable. Enter question details manually.',
    }}), {status: 409});
    expect(body.manual_details).toEqual({title: 'My question', resolution_criteria: 'Official criteria'});
    expect(body.url).toBe(imported.source_url);
    return new Response(JSON.stringify({...imported, title: body.manual_details.title, import_status: 'manual'}), {status: 201});
  });
  render(<ImportQuestion competitionId="cup" />);
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: imported.source_url}});
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Live import unavailable');
  fireEvent.change(screen.getByLabelText('Question title'), {target: {value: 'My question'}});
  fireEvent.change(screen.getByLabelText('Resolution criteria'), {target: {value: 'Official criteria'}});
  fireEvent.click(screen.getByRole('button', {name: 'Save manual question'}));
  expect(await screen.findByText('My question')).toBeInTheDocument();
  expect(screen.getByText('Saved from manual entry.')).toBeInTheDocument();
});

it('disables submission while the import is pending', async () => {
  let finish!: (response: Response) => void;
  vi.spyOn(globalThis, 'fetch').mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  render(<ImportQuestion competitionId="cup" />);
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: imported.source_url}});
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  expect(screen.getByRole('button', {name: 'Importing...'})).toBeDisabled();
  expect(screen.getByLabelText('Metaculus question URL')).toBeDisabled();
  finish(new Response(JSON.stringify(imported), {status: 201}));
  expect(await screen.findByText('Imported question')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: 'Import question'})).toBeEnabled();
});

it('retries live import when the URL changes after manual fallback', async () => {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, options) => {
    const body = JSON.parse(String(options?.body));
    if (body.url === imported.source_url) return new Response(JSON.stringify({detail: {
      code: 'manual_entry_required', message: 'Live import unavailable',
    }}), {status: 409});
    expect(body.manual_details).toBeUndefined();
    return new Response(JSON.stringify({...imported, title: 'Second question'}), {status: 201});
  });
  render(<ImportQuestion competitionId="cup" />);
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: imported.source_url}});
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  await screen.findByLabelText('Question title');
  fireEvent.change(screen.getByLabelText('Question title'), {target: {value: 'Old title'}});
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: 'https://www.metaculus.com/questions/45263/'}});
  expect(screen.queryByLabelText('Question title')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  expect(await screen.findByText('Second question')).toBeInTheDocument();
});

it('shows the imported type and deadlines with explicit unavailable dates', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify(imported), {status: 201}));
  render(<ImportQuestion competitionId="cup" />);
  fireEvent.change(screen.getByLabelText('Metaculus question URL'), {target: {value: imported.source_url}});
  fireEvent.click(screen.getByRole('button', {name: 'Import question'}));
  await screen.findByText('Imported question');
  expect(screen.getByText('Type: binary')).toBeInTheDocument();
  expect(screen.getByText('Closes: 2026-11-01T00:00:00Z')).toBeInTheDocument();
  expect(screen.getByText('Resolves: unavailable')).toBeInTheDocument();
});
