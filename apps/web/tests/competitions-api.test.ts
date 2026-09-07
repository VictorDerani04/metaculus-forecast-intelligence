import { afterEach, describe, expect, it, vi } from "vitest";

import { listCompetitions } from "../lib/api";


afterEach(() => {
  vi.restoreAllMocks();
});


describe("listCompetitions", () => {
  it("loads the authenticated user's competitions", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify([
          {
            id: "competition-1",
            name: "Metaculus Cup Fall 2026",
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

    const competitions = await listCompetitions();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/competitions",
      {
        credentials: "include",
      },
    );

    expect(competitions).toEqual([
      {
        id: "competition-1",
        name: "Metaculus Cup Fall 2026",
      },
    ]);
  });
});
