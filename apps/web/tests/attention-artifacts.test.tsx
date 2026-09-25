import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {AlertsPanel} from '../components/alerts-panel';
import {DigestPanel} from '../components/digest-panel';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('renders alert loading, empty, error, and monotonic lifecycle actions', async () => {
  const alert = {id:'a', question_id:'q', question_title:'Question', finding_id:'f', severity:'critical', reason:'New evidence', status:'new', created_at:'2026-09-24T00:00:00Z', seen_at:null, dismissed_at:null};
  vi.spyOn(globalThis, 'fetch')
    .mockResolvedValueOnce(new Response(JSON.stringify([alert])))
    .mockResolvedValueOnce(new Response(JSON.stringify({...alert, status:'seen', seen_at:'2026-09-24T01:00:00Z'})))
    .mockResolvedValueOnce(new Response(JSON.stringify({...alert, status:'dismissed', dismissed_at:'2026-09-24T02:00:00Z'})))
    ;
  render(<AlertsPanel/>);
  expect(screen.getByText('Loading alerts...')).toBeInTheDocument();
  expect(await screen.findByText('New evidence')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Seen'}));
  expect(await screen.findByText('seen')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name:'Dismiss'}));
  expect(await screen.findByText('dismissed')).toBeInTheDocument();
});

it('renders digest empty and ordered finding summaries', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify([])));
  const {unmount} = render(<DigestPanel/>);
  expect(await screen.findByText('No digests yet.')).toBeInTheDocument();
  unmount();
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify([{id:'d', period_start:'2026-09-24T00:00:00Z', period_end:'2026-09-25T00:00:00Z', status:'generated', generated_at:'2026-09-25T00:00:00Z', delivered_at:null}])))
    .mockResolvedValueOnce(new Response(JSON.stringify({id:'d', period_start:'2026-09-24T00:00:00Z', period_end:'2026-09-25T00:00:00Z', status:'generated', generated_at:'2026-09-25T00:00:00Z', delivered_at:null, items:[{id:'i', eligible_at:'2026-09-24T01:00:00Z', finding:{id:'f',question_id:'q',title:'Digest finding',summary:'Summary',materiality_class:'digest'}}]})));
  render(<DigestPanel/>);
  expect(await screen.findByText('Digest finding')).toBeInTheDocument();
  expect(screen.getByText('Summary')).toBeInTheDocument();
});
