"use client";

import { useEffect, useState } from "react";
import { SignOutButton } from "../../components/sign-out-button";
import { QuestionList } from '../../components/question-list';
import { ImportQuestion } from '../../components/import-question';

import {
  listCompetitions,
  createCompetition,
  type Competition,
  listAttention,
  type AttentionItem,
} from "../../lib/api";
import { QuestionTable } from '../../components/question-table';


type CompetitionSummary = {
  id: string;
  name: string;
  questionCount: number;
};


type CompetitionDashboardProps = {
  competitions: CompetitionSummary[];
  onImported?: (competitionId: string) => void;
};

export function CompetitionDashboard({
  competitions,
  onImported,
}: CompetitionDashboardProps) {
  return (
    <main>
      <h1>Competitions</h1>

      {competitions.map((competition) => (
        <section key={competition.id}>
          <h2>{competition.name}</h2>
          <p>
            {competition.questionCount}{" "}
            {competition.questionCount === 1 ? "question" : "questions"}
          </p>
          <QuestionList competitionId={competition.id} />
          <ImportQuestion competitionId={competition.id} onImported={() => onImported?.(competition.id)} />
        </section>
      ))}
    </main>
  );
}


export default function CompetitionsPage() {
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const [attention, setAttention] = useState<AttentionItem[] | null>(null);
  const [attentionError, setAttentionError] = useState(false);

  useEffect(() => {
    void listCompetitions().then(setCompetitions);
    void listAttention().then(setAttention).catch(() => setAttentionError(true));
  }, []);

  return (
    <>
    <SignOutButton />
    <form onSubmit={async event => {
      event.preventDefault();
      setError('');
      try {
        const created = await createCompetition(name);
        setCompetitions(current => [...current, created]);
        setName('');
      } catch {
        setError('Failed to create competition');
      }
    }}>
      <label>Competition name<input required maxLength={255} value={name} onChange={event => setName(event.target.value)} /></label>
      <button type="submit">Create competition</button>
    </form>
    {error && <p role="alert">{error}</p>}
    <CompetitionDashboard
      onImported={(id) => setCompetitions(current => current.map(competition =>
        competition.id === id ? {...competition, question_count: competition.question_count + 1} : competition
      ))}
      competitions={competitions.map((competition) => ({
        id: competition.id,
        name: competition.name,
        questionCount: competition.question_count,
      }))}
    />
    {!attention && !attentionError && <p role="status">Loading attention priorities...</p>}
    {attentionError && <p role="alert">Unable to load attention priorities.</p>}
    {attention && <QuestionTable questions={attention} />}
    </>
  );
}
