"use client";
import { useEffect, useState } from 'react';
import { getForecastRoom, type ForecastRoomData } from '../lib/api';
import { ForecastEditor } from './forecast-editor';
import { ResearchInbox } from './research-inbox';
import { ProbabilityStrip } from './probability-strip';
import { CopilotChat } from './copilot-chat';
import { ModelWorkspace } from './model-workspace';
export function ForecastRoom({questionId}: {questionId: string}) {
  const [room, setRoom] = useState<ForecastRoomData | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    getForecastRoom(questionId).then(value => {if (active) setRoom(value);})
      .catch(() => {if (active) setError('Failed to load forecast room');});
    return () => {active = false;};
  }, [questionId]);
  if (error) return <p role="alert">{error}</p>;
  if (!room) return <p role="status">Loading...</p>;
  return <main>
    <a href="/competitions">Back to competitions</a>
    <h1>{room.question.title}</h1>
    <p>{room.question.resolution_criteria ?? 'Resolution criteria unavailable'}</p>
    {room.question.source_url && <a href={room.question.source_url}>View on Metaculus</a>}
    <p>Type: {room.question.question_type ?? 'unavailable'}</p>
    <p>Closes: {room.question.close_at ?? 'unavailable'}</p>
    <p>Resolves: {room.question.resolve_at ?? 'unavailable'}</p>
    <ProbabilityStrip room={room} />
    <ModelWorkspace key={`models-${questionId}`} questionId={questionId} onRun={probability =>
      setRoom(current => current && ({...current, model_probability: probability}))} />
    <ForecastEditor questionId={questionId} current={room.human_forecast} onSaved={record =>
      setRoom(current => current && ({...current, human_forecast: record, history: [...current.history, record]}))} />
    <section aria-label="Human forecast history"><h2>Human forecast history</h2>
      {room.history.length === 0 ? <p>No human forecasts recorded yet.</p> : <ol>
        {room.history.map(record => <li key={record.id}>
          <p>{Number((record.probability * 100).toFixed(6))}%</p>
          <p>{record.rationale ?? 'No rationale provided'}</p>
          <time dateTime={record.created_at}>{record.created_at}</time>
        </li>)}
      </ol>}
    </section>
    <ResearchInbox key={questionId} questionId={questionId} />
    <CopilotChat key={`copilot-${questionId}`} questionId={questionId} />
  </main>;
}
