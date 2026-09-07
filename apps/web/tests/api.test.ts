import { afterEach, describe, expect, it, vi } from "vitest";

import { login } from "../lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("API client", () => {
  it("sends login credentials to the FastAPI backend", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          id: "user-1",
          email: "owner@example.com",
        }),
        {
          status: 200,
          headers: {
            "Content-Type": "application/json",
          },
        },
      ),
    );

    await login({
      email: "owner@example.com",
      password: "secret-password",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/auth/login",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          email: "owner@example.com",
          password: "secret-password",
        }),
      },
    );
  });
});