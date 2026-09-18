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
export type DecisionRecord = {
  id: string; user_id: string; question_id: string; competition_id: string;
  human_probability: number | null; rationale: string;
  prior_probability: number | null; model_probability: number | null;
  crowd_probability: number | null; evidence_ids: string[];
  model_spec_id: string | null; model_run_id: string | null; created_at: string;
};
export type AuditEvent = {
  id: string; action: string; entity_type: string; entity_id: string;
  question_id: string | null; details: Record<string, unknown>; created_at: string;
};
export async function listDecisions(id: string): Promise<DecisionRecord[]> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(id)}/decisions`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load decision journal');
  return response.json() as Promise<DecisionRecord[]>;
}
export async function recordDecision(id: string, rationale: string): Promise<DecisionRecord> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(id)}/decisions`, {
    method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({rationale}),
  });
  if (!response.ok) throw new Error('Failed to record decision');
  return response.json() as Promise<DecisionRecord>;
}
export async function listAuditEvents(id: string): Promise<AuditEvent[]> {
  const response = await fetch(`${API_BASE_URL}/questions/${encodeURIComponent(id)}/audit`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load audit history');
  return response.json() as Promise<AuditEvent[]>;
}
export type QuestionSummary = {id: string; competition_id: string; title: string};
export async function listQuestions(competitionId: string): Promise<QuestionSummary[]> {
  const response = await fetch(`${API_BASE_URL}/competitions/${encodeURIComponent(competitionId)}/questions`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load questions');
  return response.json() as Promise<QuestionSummary[]>;
}
export type PriorityComponent = {name: string; value: number; contribution: number};
export type AttentionItem = {
  question_id: string; title: string; competition_id: string;
  priority: {score: number; components: PriorityComponent[]; reasons: string[]};
  human_probability: number | null; model_probability: number | null;
  crowd_probability: number | null; resolve_at: string | null;
};
export async function listAttention(): Promise<AttentionItem[]> {
  const response = await fetch(`${API_BASE_URL}/competitions/attention`, {credentials: 'include'});
  if (!response.ok) throw new Error('Failed to load attention priorities');
  const payload: unknown = await response.json();
  if (!Array.isArray(payload)) return [];
  return payload.filter((item): item is AttentionItem => {
    if (!item || typeof item !== 'object') return false;
    const candidate = item as Partial<AttentionItem>;
    return typeof candidate.question_id === 'string'
      && typeof candidate.title === 'string'
      && !!candidate.priority
      && typeof candidate.priority.score === 'number'
      && Array.isArray(candidate.priority.reasons);
  });
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

export type ModelFamily = 'base_rate' | 'bayesian_likelihood_ratio' | 'weighted_driver' | 'scenario_tree' | 'seeded_monte_carlo';
export type ModelSpec = {
  id: string; user_id: string; question_id: string; family: ModelFamily; rationale: string;
  parameters: Record<string, unknown>; assumptions: string[]; evidence_ids: string[]; source_model_id: string | null;
  status: 'draft' | 'approved'; version: number; approved_at: string | null; created_at: string;
};
export type ModelRun = {
  id: string; model_spec_id: string; question_id: string; user_id: string; status: 'succeeded' | 'failed';
  probability: number | null; inputs: Record<string, unknown>; evidence_ids: string[]; model_version: number;
  spec_snapshot: Record<string, unknown>; created_at: string;
};
export type ModelSpecInput = Pick<ModelSpec, 'family' | 'rationale' | 'parameters' | 'assumptions' | 'evidence_ids'>;
async function modelRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {credentials: 'include', ...init, headers: {'Content-Type': 'application/json', ...init?.headers}});
  if (!response.ok) throw new Error('Model request failed');
  return response.json() as Promise<T>;
}
export function listModels(questionId: string): Promise<ModelSpec[]> { return modelRequest(`/questions/${encodeURIComponent(questionId)}/models`); }
export function createModel(questionId: string, payload: ModelSpecInput): Promise<ModelSpec> { return modelRequest(`/questions/${encodeURIComponent(questionId)}/models`, {method: 'POST', body: JSON.stringify(payload)}); }
export function approveModel(modelId: string): Promise<ModelSpec> { return modelRequest(`/models/${encodeURIComponent(modelId)}/activate`, {method: 'POST'}); }
export function runModel(modelId: string): Promise<ModelRun> { return modelRequest(`/models/${encodeURIComponent(modelId)}/run`, {method: 'POST'}); }
export type ChartMetadata = {model_version: number | null; generated_at: string; why_this_chart: string};
export type AnalysisData = {
  probability_history: ChartMetadata & {
    human: {timestamp: string; probability: number}[];
    model: {timestamp: string; probability: number}[];
    crowd: {timestamp: string; probability: number}[];
  };
  distribution: ChartMetadata & {
    available: boolean; probability: number | null; values: number[]; unavailable_reason: string | null;
  };
  sensitivity: ChartMetadata & {
    impacts: {name: string; baseline: number; downside: number; upside: number; impact: number}[];
  };
  evidence_impact: ChartMetadata & {
    evidence: {evidence_id: string; title: string; summary: string; dependency_warning: boolean}[];
  };
  scenarios: ChartMetadata & {scenarios: {name: string; weight: number; probability: number}[]};
  model_map: ChartMetadata & {
    nodes: {id: string; kind: string; label: string}[];
    edges: {source: string; target: string; relationship: string}[];
  };
};
export function getAnalysis(questionId: string, modelId: string): Promise<AnalysisData> {
  return modelRequest(`/questions/${encodeURIComponent(questionId)}/analysis/${encodeURIComponent(modelId)}`);
}
