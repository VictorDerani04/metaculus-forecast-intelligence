import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {NotificationPanel} from '../components/notification-panel';
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
it('loads preferences and delivery history, then persists a preference update', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce(new Response(JSON.stringify([{id:'p',user_id:'u',channel:'in_app',provider:'fake',enabled:false,immediate_alerts_enabled:false,digest_enabled:false}])))
    .mockResolvedValueOnce(new Response(JSON.stringify([{id:'a',alert_event_id:'x',digest_id:null,channel:'in_app',provider:'fake',status:'retry_wait',attempt_number:1,external_message_id:null,last_error_code:'delivery_failure',last_error_message:'safe'}])))
    .mockResolvedValueOnce(new Response(JSON.stringify({id:'p',user_id:'u',channel:'in_app',provider:'fake',enabled:true,immediate_alerts_enabled:false,digest_enabled:false})));
  render(<NotificationPanel/>);
  expect(await screen.findByText('retry_wait: delivery_failure')).toBeInTheDocument();
  fireEvent.click(screen.getByLabelText('Enable delivery'));
  expect(await screen.findByLabelText('Enable delivery')).toBeChecked();
});
it('shows a retryable load error', async () => {
  vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('{}', {status:500}));
  render(<NotificationPanel/>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load notification settings');
});
