"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  Database,
  FileText,
  RefreshCw,
  ShieldCheck,
  XCircle,
} from "lucide-react";

import { fetchDocuments, fetchLatestEval } from "@/lib/api";
import type {
  DocumentListResponse,
  EvalSummaryResponse,
  LanguageMode,
} from "@/lib/types";

export function EvalAndCorpusWorkspace({ uiLang }: { uiLang: LanguageMode }) {
  const [evalData, setEvalData] = useState<EvalSummaryResponse | null>(null);
  const [docsData, setDocsData] = useState<DocumentListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  async function loadAll() {
    setLoading(true);
    setError(null);
    try {
      const [evalRes, docsRes] = await Promise.all([
        fetchLatestEval().catch(() => null),
        fetchDocuments(),
      ]);
      setEvalData(evalRes);
      setDocsData(docsRes);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load eval & corpus telemetry.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  const filteredCases =
    evalData?.cases.filter((c) => categoryFilter === "all" || c.category === categoryFilter) ?? [];

  return (
    <div className="space-y-6">
      {/* Header & Refresh */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-100">
            {uiLang === "th"
              ? "ผลประเมิน 25-Case Golden Eval Gate และคลังเอกสาร"
              : "25-Case Golden Evaluation Gate & Active Knowledge Corpus"}
          </h2>
          <p className="text-xs text-slate-400">
            {uiLang === "th"
              ? "ตรวจสอบ Citation Hit Rate, Refusal Precision, Injection Block Rate และ Schema Pass Rate"
              : "Live telemetry from PostgreSQL eval_runs, eval_results, and ingested document_chunks."}
          </p>
        </div>
        <button
          type="button"
          onClick={() => void loadAll()}
          disabled={loading}
          className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-200 transition hover:bg-slate-800 disabled:opacity-50"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>{uiLang === "th" ? "รีเฟรชข้อมูล" : "Refresh"}</span>
        </button>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
          {error}
        </div>
      )}

      {/* Golden Eval Scorecard */}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl">
        {!evalData ? (
          <div className="text-xs text-slate-400">
            {loading
              ? "Loading Golden Eval Gate run..."
              : "No Golden Evaluation run recorded yet. Run `python eval/run_eval.py --mode ci_mock` to populate."}
          </div>
        ) : (
          <div className="space-y-5">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${
                    evalData.gate_passed
                      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                      : "border-rose-500/40 bg-rose-500/10 text-rose-300"
                  }`}
                >
                  <ShieldCheck className="h-3.5 w-3.5" />
                  {evalData.gate_passed ? "GATE PASSED" : "GATE FAILED"} ({evalData.passed_cases}/
                  {evalData.total_cases})
                </span>
                <span className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-300">
                  mode: {evalData.eval_mode}
                </span>
                <span className="rounded-md bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-300">
                  tag: {evalData.run_tag}
                </span>
              </div>
              <span className="font-mono text-xs text-slate-400">
                Avg {evalData.avg_latency_ms} ms / P95 {evalData.p95_latency_ms} ms
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <MetricCard
                label="Citation Hit Rate"
                value={`${(evalData.citation_hit_rate * 100).toFixed(1)}%`}
                target="Target >= 85%"
              />
              <MetricCard
                label="Refusal Precision"
                value={`${(evalData.refusal_precision * 100).toFixed(1)}%`}
                target="Target = 100%"
              />
              <MetricCard
                label="Injection Block Rate"
                value={`${(evalData.injection_block_rate * 100).toFixed(1)}%`}
                target="Target = 100%"
              />
              <MetricCard
                label="JSON Schema Pass"
                value={`${(evalData.json_schema_pass_rate * 100).toFixed(1)}%`}
                target="Target = 100%"
              />
            </div>

            {/* Filter & Case Table */}
            <div className="space-y-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Per-Case Breakdown ({filteredCases.length})
                </h3>
                <select
                  value={categoryFilter}
                  onChange={(e) => setCategoryFilter(e.target.value)}
                  className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                >
                  <option value="all">All categories (25)</option>
                  <option value="thai_in_scope">thai_in_scope</option>
                  <option value="english_in_scope">english_in_scope</option>
                  <option value="code_mixed_th_en">code_mixed_th_en</option>
                  <option value="out_of_scope_unanswerable">out_of_scope_unanswerable</option>
                  <option value="prompt_injection">prompt_injection</option>
                  <option value="ticket_triage">ticket_triage</option>
                </select>
              </div>

              <div className="max-h-72 overflow-auto rounded-xl border border-slate-800">
                <table className="w-full text-left text-xs">
                  <thead className="sticky top-0 bg-slate-950 text-[11px] uppercase text-slate-400">
                    <tr>
                      <th className="px-3 py-2">Case</th>
                      <th className="px-3 py-2">Category</th>
                      <th className="px-3 py-2">Lang</th>
                      <th className="px-3 py-2">Expected</th>
                      <th className="px-3 py-2">Actual</th>
                      <th className="px-3 py-2 text-right">Latency</th>
                      <th className="px-3 py-2 text-center">Pass</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/80 bg-slate-900/40">
                    {filteredCases.map((c) => (
                      <tr key={c.case_id} className="hover:bg-slate-800/40">
                        <td className="px-3 py-2 font-mono text-slate-200">{c.case_id}</td>
                        <td className="px-3 py-2 font-mono text-slate-300">{c.category}</td>
                        <td className="px-3 py-2 font-mono text-slate-400">{c.language}</td>
                        <td className="px-3 py-2 font-mono text-slate-300">{c.expected_outcome}</td>
                        <td className="px-3 py-2 font-mono text-slate-200">{c.actual_outcome}</td>
                        <td className="px-3 py-2 text-right font-mono text-slate-400">
                          {c.latency_ms} ms
                        </td>
                        <td className="px-3 py-2 text-center">
                          {c.passed ? (
                            <CheckCircle2 className="mx-auto h-4 w-4 text-emerald-400" />
                          ) : (
                            <XCircle className="mx-auto h-4 w-4 text-rose-400" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Active Knowledge Corpus */}
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Database className="h-4 w-4 text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-100">
              {uiLang === "th" ? "คลังเอกสารที่เปิดใช้งาน (Active Corpus)" : "Active Knowledge Corpus"}
            </h3>
          </div>
          {docsData && (
            <span className="font-mono text-xs text-slate-300">
              {docsData.total_documents} docs • {docsData.total_chunks} chunks
            </span>
          )}
        </div>

        {!docsData ? (
          <div className="text-xs text-slate-400">
            {loading ? "Loading corpus inventory..." : "Unable to load corpus inventory."}
          </div>
        ) : (
          <div className="max-h-72 overflow-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-950 text-[11px] uppercase text-slate-400">
                <tr>
                  <th className="px-3 py-2">Source Key</th>
                  <th className="px-3 py-2">Title</th>
                  <th className="px-3 py-2">Lang</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2 text-right">Chunks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 bg-slate-900/40">
                {docsData.documents.map((doc) => (
                  <tr key={doc.document_id} className="hover:bg-slate-800/40">
                    <td className="px-3 py-2 font-mono text-indigo-300">
                      <span className="inline-flex items-center gap-1.5">
                        <FileText className="h-3.5 w-3.5 text-slate-500" />
                        {doc.source_key}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-slate-200">{doc.title}</td>
                    <td className="px-3 py-2 font-mono text-slate-400">{doc.language}</td>
                    <td className="px-3 py-2 font-mono text-slate-300">{doc.doc_type}</td>
                    <td className="px-3 py-2 text-right font-mono text-slate-200">
                      {doc.chunk_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  target,
}: {
  label: string;
  value: string;
  target: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-3.5">
      <div className="text-[11px] text-slate-400">{label}</div>
      <div className="mt-1 font-mono text-xl font-bold text-emerald-300">{value}</div>
      <div className="mt-0.5 font-mono text-[10px] text-slate-500">{target}</div>
    </div>
  );
}
