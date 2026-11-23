"""Synchronous FastAPI route handler for Golden Evaluation Gate results."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from app.db import DatabaseManager
from app.schemas.eval import EvalCaseResult, EvalSummaryResponse

router = APIRouter(prefix="/api/v1/eval", tags=["eval"])


@router.get("/latest", response_model=EvalSummaryResponse)
def get_latest_eval_run(request: Request) -> EvalSummaryResponse:
    """Fetch the most recent Golden Eval run and its per-case results (sync threadpool)."""
    db: DatabaseManager = request.app.state.db
    with db.connection() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                id,
                run_tag,
                git_sha,
                eval_mode,
                model_name,
                embedding_model,
                total_cases,
                passed_cases,
                citation_hit_rate,
                refusal_precision,
                injection_block_rate,
                json_schema_pass_rate,
                avg_latency_ms,
                p95_latency_ms,
                total_cost_usd,
                cost_per_1k_requests_usd,
                gate_passed,
                notes,
                created_at
            FROM eval_runs
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        run_row = cur.fetchone()
        if not run_row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No Golden Evaluation runs recorded yet.",
            )

        cur.execute(
            """
            SELECT
                case_id,
                category,
                language,
                expected_outcome,
                actual_outcome,
                passed,
                citation_hit,
                schema_valid,
                expected_source_keys,
                actual_source_keys,
                latency_ms,
                input_tokens,
                output_tokens,
                estimated_cost_usd,
                failure_reason
            FROM eval_results
            WHERE eval_run_id = %s
            ORDER BY case_id ASC
            """,
            (run_row["id"],),
        )
        case_rows = cur.fetchall()

    cases = [
        EvalCaseResult(
            case_id=str(row["case_id"]),
            category=row["category"],
            language=row["language"],
            expected_outcome=row["expected_outcome"],
            actual_outcome=row["actual_outcome"],
            passed=bool(row["passed"]),
            citation_hit=row["citation_hit"],
            schema_valid=row["schema_valid"],
            expected_source_keys=list(row["expected_source_keys"] or []),
            actual_source_keys=list(row["actual_source_keys"] or []),
            latency_ms=int(row["latency_ms"]),
            input_tokens=int(row["input_tokens"] or 0),
            output_tokens=int(row["output_tokens"] or 0),
            estimated_cost_usd=float(row["estimated_cost_usd"] or 0.0),
            failure_reason=row["failure_reason"],
        )
        for row in case_rows
    ]

    return EvalSummaryResponse(
        eval_run_id=run_row["id"],
        run_tag=str(run_row["run_tag"]),
        git_sha=run_row["git_sha"],
        eval_mode=run_row["eval_mode"],
        model_name=str(run_row["model_name"]),
        embedding_model=str(run_row["embedding_model"]),
        total_cases=int(run_row["total_cases"]),
        passed_cases=int(run_row["passed_cases"]),
        citation_hit_rate=float(run_row["citation_hit_rate"]),
        refusal_precision=float(run_row["refusal_precision"]),
        injection_block_rate=float(run_row["injection_block_rate"]),
        json_schema_pass_rate=float(run_row["json_schema_pass_rate"]),
        avg_latency_ms=int(run_row["avg_latency_ms"]),
        p95_latency_ms=int(run_row["p95_latency_ms"]),
        total_cost_usd=float(run_row["total_cost_usd"] or 0.0),
        cost_per_1k_requests_usd=float(run_row["cost_per_1k_requests_usd"] or 0.0),
        gate_passed=bool(run_row["gate_passed"]),
        notes=run_row["notes"],
        created_at=run_row["created_at"],
        cases=cases,
    )
