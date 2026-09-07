import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginForm } from "../app/login/page";

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