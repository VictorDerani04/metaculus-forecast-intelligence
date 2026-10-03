import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CompetitionDashboard } from "../app/competitions/page";
import { SignOutButton } from "../components/sign-out-button";


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

it("signs out and returns to the login page", async () => {
  const onLogout = vi.fn().mockResolvedValue(undefined);
  const onSignedOut = vi.fn();

  render(<SignOutButton onLogout={onLogout} onSignedOut={onSignedOut} />);
  screen.getByRole("button", {name: "Sign out"}).click();

  await vi.waitFor(() => expect(onLogout).toHaveBeenCalledOnce());
  expect(onSignedOut).toHaveBeenCalledOnce();
});

it("shows a safe error when sign out fails", async () => {
  render(<SignOutButton onLogout={vi.fn().mockRejectedValue(new Error("network detail"))} />);

  screen.getByRole("button", {name: "Sign out"}).click();

  expect(await screen.findByRole("alert")).toHaveTextContent("Unable to sign out. Please try again.");
});
