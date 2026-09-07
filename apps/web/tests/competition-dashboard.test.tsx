import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { CompetitionDashboard } from "../app/competitions/page";


afterEach(cleanup);


describe("CompetitionDashboard", () => {
  it("shows competitions with their question counts", () => {
    render(
      <CompetitionDashboard
        competitions={[
          {
            id: "competition-1",
            name: "Metaculus Cup Fall 2026",
            questionCount: 12,
          },
        ]}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Metaculus Cup Fall 2026",
      }),
    ).toBeTruthy();

    expect(screen.getByText("12 questions")).toBeTruthy();
  });
});
