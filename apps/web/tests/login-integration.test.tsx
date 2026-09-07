import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { login } from "../lib/api";
import LoginPage from "../app/login/page";

const replaceMock = vi.fn();

vi.mock("../lib/api", () => ({
  login: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: replaceMock,
  }),
}));

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("login integration", () => {
  it("authenticates and navigates to the private workspace", async () => {
    vi.mocked(login).mockResolvedValue({
      id: "user-1",
      email: "owner@example.com",
    });

    render(<LoginPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "owner@example.com" },
    });

    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret-password" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(login).toHaveBeenCalledWith({
        email: "owner@example.com",
        password: "secret-password",
      });
    });

    expect(replaceMock).toHaveBeenCalledWith("/");
  });
});