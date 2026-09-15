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

export type ImportedQuestion = {
  id: string;
  competition_id: string;
  title: string;
  source_post_id: number;
  source_url: string;
  resolution_criteria: string | null;
  question_type: string | null;
  close_at: string | null;
  resolve_at: string | null;
  crowd_probability: number | null;
  import_status: 'imported' | 'partial' | 'manual';
};

export class ImportError extends Error {
  constructor(message: string, public code: string) { super(message); }
}

export type ManualQuestionDetails = { title: string; resolution_criteria: string };

export async function importQuestion(competitionId: string, url: string, manual_details?: ManualQuestionDetails): Promise<ImportedQuestion> {
  const response = await fetch(`${API_BASE_URL}/competitions/${encodeURIComponent(competitionId)}/questions/import`, {
    method: 'POST',
    credentials: 'include',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({url, ...(manual_details ? {manual_details} : {})}),
  });
  if (!response.ok) {
    const body = await response.json();
    throw new ImportError(body.detail?.message ?? 'Import failed', body.detail?.code ?? 'import_failed');
  }
  return response.json() as Promise<ImportedQuestion>;
}


export async function createCompetition(name: string): Promise<Competition> {
  const response = await fetch(`${API_BASE_URL}/competitions`, {
    method: 'POST', credentials: 'include',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({name}),
  });
  if (!response.ok) throw new Error('Failed to create competition');
  return response.json() as Promise<Competition>;
}
export type HumanForecast = {
  id: number; question_id: string; user_id: string; probability: number;
  rationale: string | null; created_at: string;
};
export type ForecastRoomData = {
  question: {id: string; competition_id: string; title: string; source_url: string | null;
    resolution_criteria: string | null; question_type: string | null; close_at: string | null; resolve_at: string | null};
  prior_probability: number | null; model_probability: number | null;
  human_forecast: HumanForecast | null; community_probability: number | null; history: HumanForecast[];
};
export async function getForecastRoom(id: string): Promise<ForecastRoomData> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(id)}/room`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load forecast room');
  return response.json() as Promise<ForecastRoomData>;
}
export async function saveHumanForecast(id: string, probability: number, rationale: string | null): Promise<HumanForecast> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(id)}/forecasts`, {
    method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({probability, rationale}),
  });
  if (!response.ok) throw new Error('Failed to save human forecast');
  return response.json() as Promise<HumanForecast>;
}
export type QuestionSummary = {id: string; competition_id: string; title: string};
export async function listQuestions(competitionId: string): Promise<QuestionSummary[]> {
  const response = await fetch(`${API_BASE_URL}/competitions/${encodeURIComponent(competitionId)}/questions`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load questions');
  return response.json() as Promise<QuestionSummary[]>;
}

export type ResearchStatus = 'candidate' | 'approved' | 'rejected' | 'deferred' | 'duplicate' | 'superseded';
export type ResearchDecision = {id: number; user_id: string; decision: ResearchStatus; created_at: string; related_item_id: string | null};
export type CandidateInput = {question_id: string; title: string; summary: string; source_url: string; source_name: string};
export type ResearchItem = CandidateInput & {id: string; user_id: string; status: ResearchStatus; created_at: string; decisions: ResearchDecision[]};
export type Evidence = CandidateInput & {id: string; user_id: string; research_item_id: string; decision: 'approved'; approved_at: string; dependency_evidence_ids: string[]};
export type ResearchData = {items: ResearchItem[]; evidence: Evidence[]};
export async function getResearch(questionId: string): Promise<ResearchData> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(questionId)}/research`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load research');
  return response.json() as Promise<ResearchData>;
}
export async function addResearchCandidate(payload: CandidateInput): Promise<ResearchItem> {
  const response = await fetch(`${API_BASE_URL}/research-items`, {
    method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Failed to add candidate');
  return response.json() as Promise<ResearchItem>;
}
export type ResearchDecisionInput = {decision: Exclude<ResearchStatus, 'candidate'>; related_item_id?: string; dependency_evidence_ids?: string[]};
export async function decideResearch(itemId: string, payload: ResearchDecisionInput): Promise<ResearchItem> {
  const response = await fetch(`${API_BASE_URL}/research-items/${encodeURIComponent(itemId)}/decision`, {
    method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('Failed to record research decision');
  return response.json() as Promise<ResearchItem>;
}

export type CopilotMessage = {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
};
export type CopilotActionProposal = {
  action: string;
  summary: string;
};
export type CopilotHistory = {messages: CopilotMessage[]};
export type CopilotExchange = {
  user_message: CopilotMessage;
  assistant_message: CopilotMessage;
  proposed_actions: CopilotActionProposal[];
};
export async function getCopilotHistory(questionId: string): Promise<CopilotHistory> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(questionId)}/chat`, {
    credentials: 'include',
  });
  if (!response.ok) throw new Error('Failed to load copilot history');
  return response.json() as Promise<CopilotHistory>;
}
export async function sendCopilotMessage(questionId: string, content: string): Promise<CopilotExchange> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(questionId)}/chat`, {
    method: 'POST',
    credentials: 'include',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({content}),
  });
  if (!response.ok) throw new Error('Failed to send copilot message');
  return response.json() as Promise<CopilotExchange>;
}
