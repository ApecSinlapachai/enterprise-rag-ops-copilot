import type {
  DocumentListResponse,
  EvalSummaryResponse,
  HealthResponse,
  RAGQueryRequest,
  RAGQueryResponse,
  TriageTicketRequest,
  TriageTicketResponse,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/+$/, "") ||
  "http://localhost:8000";

export const API_PROXY_PREFIX = (
  process.env.NEXT_PUBLIC_API_PROXY_PREFIX || "/backend"
).replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;
  retryAfterSeconds?: number;

  constructor(message: string, status: number, retryAfterSeconds?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: HeadersInit = {
    ...(init?.body !== undefined ? { "Content-Type": "application/json" } : {}),
    ...(init?.headers ?? {}),
  };

  const response = await fetch(`${API_PROXY_PREFIX}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (!response.ok) {
    const retryAfterHeader = response.headers.get("Retry-After");
    const retryAfter = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : undefined;
    let detail = `Request failed (${response.status})`;
    try {
      const errBody = (await response.json()) as { detail?: string };
      if (errBody?.detail) {
        detail = errBody.detail;
      }
    } catch {
      // Keep default status message when body is non-JSON.
    }
    throw new ApiError(detail, response.status, Number.isNaN(retryAfter) ? undefined : retryAfter);
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health", { method: "GET" });
}

export function queryRag(payload: RAGQueryRequest): Promise<RAGQueryResponse> {
  return requestJson<RAGQueryResponse>("/api/v1/rag/query", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitTriage(payload: TriageTicketRequest): Promise<TriageTicketResponse> {
  return requestJson<TriageTicketResponse>("/api/v1/triage", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fetchDocuments(): Promise<DocumentListResponse> {
  return requestJson<DocumentListResponse>("/api/v1/documents", { method: "GET" });
}

export function fetchLatestEval(): Promise<EvalSummaryResponse> {
  return requestJson<EvalSummaryResponse>("/api/v1/eval/latest", { method: "GET" });
}
