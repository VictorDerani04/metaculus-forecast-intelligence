import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import CompetitionsPage from "../app/competitions/page";


afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});


describe("CompetitionsPage", () => {
  it("loads and displays competitions from the API", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "competition-1",
            name: "Metaculus Cup Fall 2026",
            question_count: 1,
          },
        ]),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    render(<CompetitionsPage />);

    expect(
      await screen.findByRole("heading", {
        name: "Metaculus Cup Fall 2026",
      }),
    ).toBeTruthy();

    expect(screen.getByText("1 question")).toBeTruthy();
  });
});
