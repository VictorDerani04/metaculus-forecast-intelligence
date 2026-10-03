import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "../app/login/page";
import { AuthenticationError } from "../lib/api";

afterEach(() => {
  cleanup();
});

describe("login page", () => {
  it("renders email and password fields and submits credentials", async () => {
    const onLogin = vi.fn().mockResolvedValue(undefined);

    render(<LoginForm onLogin={onLogin} />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "owner@example.com" },
    });

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret-password" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(onLogin).toHaveBeenCalledWith({
      email: "owner@example.com",
      password: "secret-password",
    });
  });

  it("shows a safe failure message and prevents a duplicate submission", async () => {
    let resolveLogin: (() => void) | undefined;
    const onLogin = vi.fn().mockImplementation(() => new Promise<void>((resolve) => {
      resolveLogin = resolve;
    }));

    render(<LoginForm onLogin={onLogin} />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Signing in…" }));
    expect(onLogin).toHaveBeenCalledTimes(1);

    resolveLogin?.();
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled());
  });

  it("renders a failed sign-in message", async () => {
    render(<LoginForm onLogin={vi.fn().mockRejectedValue(
      new AuthenticationError("invalid_credentials", "Invalid email or password."),
    )} />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password.");
  });

  it("does not display unexpected error details", async () => {
    render(<LoginForm onLogin={vi.fn().mockRejectedValue(new Error("internal parser detail"))} />);

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to sign in. Please try again.");
    expect(screen.queryByText("internal parser detail")).not.toBeInTheDocument();
  });
});

it("uses the API login function and redirects after successful sign in", async () => {
  const loginMock = vi.fn().mockResolvedValue({
    id: "user-1",
    email: "owner@example.com",
  });

  const replaceMock = vi.fn();

  render(
    <LoginForm
      onLogin={async (credentials) => {
        await loginMock(credentials);
        replaceMock("/");
      }}
    />,
  );

  fireEvent.change(screen.getByLabelText("Email"), {
    target: { value: "owner@example.com" },
  });

  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "secret-password" },
  });

  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

  await vi.waitFor(() => {
    expect(loginMock).toHaveBeenCalledWith({
      email: "owner@example.com",
      password: "secret-password",
    });

    expect(replaceMock).toHaveBeenCalledWith("/");
  });
});
