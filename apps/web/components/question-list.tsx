"use client";
import { useState } from 'react';
import { listQuestions, type QuestionSummary } from '../lib/api';
export function QuestionList({competitionId}: {competitionId: string}) {
  const [questions, setQuestions] = useState<QuestionSummary[] | null>(null);
  const [error, setError] = useState('');
  return <div>
    <button type="button" onClick={async () => {
      setError('');
      try {setQuestions(await listQuestions(competitionId));}
      catch {setError('Failed to load questions');}
    }}>View questions</button>
    {error && <p role="alert">{error}</p>}
    {questions?.length === 0 && <p>No questions saved yet.</p>}
    {questions && <ul>{questions.map(question => <li key={question.id}>
      <a href={`/questions/${encodeURIComponent(question.id)}`}>{question.title}</a>
    </li>)}</ul>}
  </div>;
}
