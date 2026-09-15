"use client";
import { useEffect, useState, type FormEvent } from 'react';
import {
  getCopilotHistory,
  sendCopilotMessage,
  type CopilotMessage,
} from '../lib/api';

export function CopilotChat({questionId}: {questionId: string}) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [draft, setDraft] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [historyError, setHistoryError] = useState(false);

  useEffect(() => {
    let active = true;
    getCopilotHistory(questionId)
      .then(history => { if (active) setMessages(history.messages ?? []); })
      .catch(() => { if (active) setHistoryError(true); });
    return () => { active = false; };
  }, [questionId]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending || !draft.trim()) return;
    const content = draft;
    setPending(true);
    setError('');
    try {
      const exchange = await sendCopilotMessage(questionId, content);
      setMessages(current => [...current, exchange.user_message, exchange.assistant_message]);
      setDraft('');
    } catch {
      setError('Copilot is unavailable. Try again.');
    } finally {
      setPending(false);
    }
  }

  return <section aria-label="Copilot">
    <h2>Copilot</h2>
    <p>Ask for advisory analysis of this question. Copilot cannot change forecasts or evidence.</p>
    {historyError && <p role="status">Previous Copilot messages are unavailable.</p>}
    {error && <p role="alert">{error}</p>}
    {messages.length > 0 && <ol aria-label="Copilot conversation">
      {messages.map(message => <li key={message.id}>
        <strong>{message.role === 'user' ? 'You' : 'Copilot'}</strong>
        <p>{message.content}</p>
      </li>)}
    </ol>}
    <form onSubmit={submit}>
      <label>Copilot message
        <textarea
          disabled={pending}
          value={draft}
          onChange={event => setDraft(event.target.value)}
        />
      </label>
      <button disabled={pending || !draft.trim()} type="submit">
        {pending ? 'Sending...' : 'Send message'}
      </button>
    </form>
  </section>;
}
