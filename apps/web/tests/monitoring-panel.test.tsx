import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {MonitoringPanel} from '../components/monitoring-panel';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('shows truthful latest finding and candidate counts', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({id:'m', enabled:true, monitoring_interval_minutes:60, last_run_at:null, last_success_at:null, next_run_at:null, latest_run:{id:'r',job_id:'j',status:'succeeded',started_at:'',completed_at:'',safe_error_summary:null,normalized_findings:2,candidates_created:1}})));
  render(<MonitoringPanel questionId="q"/>);
  expect(await screen.findByText('Latest findings: 2')).toBeInTheDocument();
  expect(screen.getByText('Latest candidates: 1')).toBeInTheDocument();
});

it('shows loading, empty, failure, enable, disable, and monitor-now states', async () => {
  let resolveFetch!: (response: Response) => void;
  vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => new Promise(resolve => { resolveFetch = resolve; }));
  render(<MonitoringPanel questionId="q"/>);
  expect(screen.getByText('Loading monitoring...')).toBeInTheDocument();
  resolveFetch(new Response(JSON.stringify({id:'m', enabled:false, monitoring_interval_minutes:60, last_run_at:null, last_success_at:null, next_run_at:null, latest_run:null})));
  expect(await screen.findByText('Last checked: Never checked')).toBeInTheDocument();
  expect(screen.getByRole('button', {name:'Enable monitoring'})).toBeInTheDocument();
});

it('shows a retryable API error instead of silently hiding it', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', {status: 500}));
  render(<MonitoringPanel questionId="q"/>);
  expect(await screen.findByText('Unable to load monitoring. Please retry.')).toBeInTheDocument();
});

it('enables, disables, and runs monitoring actions', async () => {
  const disabled = {id:'m', enabled:false, monitoring_interval_minutes:60, last_run_at:null, last_success_at:null, next_run_at:null, latest_run:null};
  const enabled = {...disabled, enabled:true};
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify(disabled)))
    .mockResolvedValueOnce(new Response(JSON.stringify(enabled)))
    .mockResolvedValueOnce(new Response(JSON.stringify(enabled)))
    .mockResolvedValueOnce(new Response(JSON.stringify({job_id:'j', status:'queued'})))
    .mockResolvedValueOnce(new Response(JSON.stringify(enabled)))
    .mockResolvedValueOnce(new Response(JSON.stringify(disabled)))
    .mockResolvedValueOnce(new Response(JSON.stringify(disabled)));
  render(<MonitoringPanel questionId="q"/>);
  fireEvent.click(await screen.findByRole('button', {name:'Enable monitoring'}));
  expect(await screen.findByRole('button', {name:'Monitor now'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Monitor now'}));
  expect(await screen.findByRole('button', {name:'Disable monitoring'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Disable monitoring'}));
  expect(await screen.findByRole('button', {name:'Enable monitoring'})).toBeInTheDocument();
});
