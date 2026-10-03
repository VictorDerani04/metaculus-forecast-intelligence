"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import {
  AuthenticationError,
  login,
  type LoginCredentials,
} from "../../lib/api";

type LoginFormProps = {
  onLogin: (credentials: LoginCredentials) => void | Promise<void>;
};

export function LoginForm({ onLogin }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isSubmitting) return;
    setError("");
    setIsSubmitting(true);

    try {
      await onLogin({email, password});
    } catch (caught) {
      setError(
        caught instanceof AuthenticationError
          ? caught.message
          : "Unable to sign in. Please try again.",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main>
      <h1>Sign in</h1>

      <form onSubmit={handleSubmit}>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </label>

        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>

        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

export default function LoginPage() {
  const router = useRouter();

  async function handleLogin(credentials: LoginCredentials) {
    await login(credentials);
    router.replace("/competitions");
  }

  return <LoginForm onLogin={handleLogin} />;
}
