"use client";

import { useEffect, useState } from "react";
import { ImportQuestion } from '../../components/import-question';

import {
  listCompetitions,
  createCompetition,
  type Competition,
} from "../../lib/api";


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

  useEffect(() => {
    void listCompetitions().then(setCompetitions);
  }, []);

  return (
    <>
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
    </>
  );
}
