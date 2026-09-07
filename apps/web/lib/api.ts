export type LoginCredentials = {
  email: string;
  password: string;
};

export type AuthenticatedUser = {
  id: string;
  email: string;
};

export type Competition = {
  id: string;
  name: string;
  question_count: number;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";


export async function login(
  credentials: LoginCredentials,
): Promise<AuthenticatedUser> {
  const response = await fetch(`${API_BASE_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    credentials: "include",
    body: JSON.stringify(credentials),
  });

  if (!response.ok) {
    throw new Error("Login failed");
  }

  return response.json() as Promise<AuthenticatedUser>;
}


export async function listCompetitions(): Promise<Competition[]> {
  const response = await fetch(`${API_BASE_URL}/competitions`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Failed to load competitions");
  }

  return response.json() as Promise<Competition[]>;
}
