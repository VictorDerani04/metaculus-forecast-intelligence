import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { HomeScreen } from "../app/page";

afterEach(() => {
  cleanup();
});

describe("private application shell", () => {
  it("shows a login path when no authenticated user exists", () => {
    render(<HomeScreen user={null} />);

    expect(
      screen.getByRole("heading", {
        name: "Private Forecasting Workspace",
      }),
    ).toBeInTheDocument();

    expect(
      screen.getByRole("link", { name: "Sign in" }),
    ).toHaveAttribute("href", "/login");
  });

  it("renders Forecast Intelligence for the authenticated private user", () => {
    render(
      <HomeScreen
        user={{
          id: "user-1",
          email: "owner@example.com",
        }}
      />,
    );

    expect(
      screen.getByRole("heading", {
        name: "Forecast Intelligence",
      }),
    ).toBeInTheDocument();

    expect(screen.getByText("owner@example.com")).toBeInTheDocument();
  });
});