"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import {
  login,
  type LoginCredentials,
} from "../../lib/api";

type LoginFormProps = {
  onLogin: (credentials: LoginCredentials) => void | Promise<void>;
};

export function LoginForm({ onLogin }: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    void onLogin({
      email,
      password,
    });
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

        <button type="submit">Sign in</button>
      </form>
    </main>
  );
}

export default function LoginPage() {
  const router = useRouter();

  async function handleLogin(credentials: LoginCredentials) {
    await login(credentials);
    router.replace("/");
  }

  return <LoginForm onLogin={handleLogin} />;
}