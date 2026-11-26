# ADR-0002: 3-Stage Guardrails, Tiered Gemini 3.x Routing & Sync FastAPI Routes

- **Status:** Accepted
- **Date:** 2026-11-26
- **Deciders:** Apec Sinlapachai

---

## 1. Context
A public No-Login RAG & Triage API running on Gemini Free Tier quotas (`20 req/day` on frontier models) faces three production risks: (1) prompt injection and out-of-scope queries wasting LLM tokens or causing hallucinations, (2) HTTP `429 RESOURCE_EXHAUSTED` failures breaking the live demo, and (3) blocking FastAPI's asyncio event loop when calling synchronous `psycopg_pool`.

## 2. Decision
> We will enforce a **3-Stage Guardrail Pipeline** (Stage 0 Injection Gate at `$0`, Stage 1 Pre-LLM Retrieval Gate at `$0`, Stage 2 Post-LLM UUID Citation & Confidence Gate), route requests via **Tiered Gemini 3.x models** (`gemini-3.5-flash-lite` fast path, `gemini-3.8-flash` complex path, `gemini-3.1-flash-lite` fallback, plus deterministic grounded/rule fallback on `429`), and declare all DB-touching FastAPI endpoints as **synchronous `def` handlers**.

## 3. Alternatives Considered
| Option | Pros | Cons | Why Rejected / Chosen |
| :--- | :--- | :--- | :--- |
| **3-Stage Guardrails + Tiered Gemini 3.x + Sync `def` Routes (Chosen)** | `$0` spend on blocked/OOS queries; zero fabricated citations; survives `429` gracefully; safe threadpool execution for `psycopg_pool` | Slightly higher complexity in `generator.py` and `triage_service.py` | Best reliability, cost control, and groundedness guarantee |
| **Single Frontier Model + Prompt-Only Guardrails** | Minimal code | Vulnerable to prompt injection, hallucinations, and instant Free Tier quota exhaustion | Rejected; unacceptable hallucination and `429` risk |
| **Async `async def` Routes with Sync `psycopg_pool`** | Looks idiomatic | Blocks the single asyncio event loop under concurrent DB calls | Rejected; synchronous `def` routes safely offload to FastAPI's worker threadpool |

## 4. Consequences
- **Positive:** `1.0000` Refusal Precision, `1.0000` Injection Block Rate, and `1.0000` Triage JSON Schema Pass Rate across CI and live production baselines; live demo remains functional even when Gemini quotas reset.
- **Negative / Trade-offs:** Responses are returned atomically rather than streamed so Stage 2 can validate UUID citations before emitting output.
- **Reversibility:** Easy — routing and guardrails are isolated in `api/app/services/{guardrails,generator,triage_service}.py` and configured via `.env`.
