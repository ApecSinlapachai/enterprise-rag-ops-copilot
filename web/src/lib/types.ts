export type LanguageMode = "th" | "en";

export type GroundingStatus =
  | "ANSWERED"
  | "REFUSED_LOW_EVIDENCE"
  | "BLOCKED_INJECTION"
  | "ERROR_FALLBACK";

export interface HealthResponse {
  status: string;
  version: string;
  database_connected: boolean;
}

export interface CitationItem {
  chunk_id: string;
  source_key: string;
  doc_title: string;
  section_path: string;
  snippet: string;
  vec_similarity: number;
  fts_rank: number;
  rrf_score: number;
}

export interface RAGQueryRequest {
  query: string;
  language_hint: "auto" | "th" | "en";
}

export interface RAGQueryResponse {
  request_id: string;
  query_language: "th" | "en" | "mixed" | "unknown";
  grounding_status: GroundingStatus;
  answer: string;
  refusal_reason: string | null;
  confidence_score: number;
  citations: CitationItem[];
  retrieval_ms: number;
  generation_ms: number;
  total_latency_ms: number;
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
}

export interface TriageTicketRequest {
  message: string;
  source_channel: "web_demo" | "line" | "email" | "api" | "eval";
}

export interface TriageTicketResponse {
  ticket_id: string;
  request_id: string;
  language_detected: "th" | "en" | "mixed";
  category:
    | "billing_refund"
    | "technical_incident"
    | "account_access"
    | "sla_escalation"
    | "feature_request"
    | "general_inquiry"
    | "prompt_injection_attempt";
  urgency_score: number;
  priority: "P0" | "P1" | "P2" | "P3";
  sentiment: "negative" | "neutral" | "positive";
  summary: string;
  suggested_action: string;
  suggested_team:
    | "l1_support"
    | "l2_engineering"
    | "billing_ops"
    | "security_ops"
    | "account_management";
  requires_human_review: boolean;
  extracted_entities: Record<string, string>;
  validation_status: "pydantic_passed" | "repaired_retry" | "deterministic_fallback";
  model_name: string;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  latency_ms: number;
}

export interface DocumentListItem {
  document_id: string;
  source_key: string;
  title: string;
  language: "th" | "en" | "bilingual";
  doc_type: "sop" | "sla" | "faq" | "security_policy" | "runbook" | "pricing";
  version: string;
  is_active: boolean;
  chunk_count: number;
  updated_at: string;
}

export interface DocumentListResponse {
  total_documents: number;
  total_chunks: number;
  documents: DocumentListItem[];
}

export interface EvalCaseResult {
  case_id: string;
  category:
    | "thai_in_scope"
    | "english_in_scope"
    | "code_mixed_th_en"
    | "out_of_scope_unanswerable"
    | "prompt_injection"
    | "ticket_triage";
  language: "th" | "en" | "mixed";
  expected_outcome: string;
  actual_outcome: string;
  passed: boolean;
  citation_hit: boolean | null;
  schema_valid: boolean | null;
  expected_source_keys: string[];
  actual_source_keys: string[];
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  failure_reason: string | null;
}

export interface EvalSummaryResponse {
  eval_run_id: string;
  run_tag: string;
  git_sha: string | null;
  eval_mode: "live_gemini" | "ci_mock" | "hybrid_replay";
  model_name: string;
  embedding_model: string;
  total_cases: number;
  passed_cases: number;
  citation_hit_rate: number;
  refusal_precision: number;
  injection_block_rate: number;
  json_schema_pass_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  total_cost_usd: number;
  cost_per_1k_requests_usd: number;
  gate_passed: boolean;
  notes: string | null;
  created_at: string;
  cases: EvalCaseResult[];
}
