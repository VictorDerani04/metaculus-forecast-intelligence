"use client";

import { useEffect, useState } from "react";

import {
  listCompetitions,
  type Competition,
} from "../../lib/api";


type CompetitionSummary = {
  id: string;
  name: string;
  questionCount: number;
};


type CompetitionDashboardProps = {
  competitions: CompetitionSummary[];
};


export function CompetitionDashboard({
  competitions,
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
        </section>
      ))}
    </main>
  );
}


export default function CompetitionsPage() {
  const [competitions, setCompetitions] = useState<Competition[]>([]);

  useEffect(() => {
    void listCompetitions().then(setCompetitions);
  }, []);

  return (
    <CompetitionDashboard
      competitions={competitions.map((competition) => ({
        id: competition.id,
        name: competition.name,
        questionCount: competition.question_count,
      }))}
    />
  );
}
