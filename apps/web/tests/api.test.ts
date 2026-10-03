import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthenticationError, login, logout } from "../lib/api";

afterEach(() => {
  vi.restoreAllMocks();
});

it("classifies invalid credentials without exposing backend detail", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(
    JSON.stringify({detail: "Invalid email or password"}),
    {status: 401},
  ));

  await expect(login({email: "owner@example.com", password: "wrong"})).rejects.toEqual(
    new AuthenticationError("invalid_credentials", "Invalid email or password."),
  );
});

it("reports an unavailable API when the login request cannot connect", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Network error"));

  await expect(login({email: "owner@example.com", password: "secret"})).rejects.toEqual(
    new AuthenticationError("api_unavailable", "Unable to reach the sign-in service. Please try again."),
  );
});

it("does not expose malformed successful responses", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("not-json", {status: 200}));

  await expect(login({email: "owner@example.com", password: "secret"})).rejects.toEqual(
    new AuthenticationError("unexpected", "Unable to sign in. Please try again."),
  );
});

it("sends a credentialed logout request", async () => {
  const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, {status: 204}));

  await logout();

  expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/auth/logout", {
    method: "POST",
    credentials: "include",
  });
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
