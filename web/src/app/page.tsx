"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  BarChart3,
  Bot,
  Github,
  Languages,
  RefreshCw,
  Ticket,
} from "lucide-react";

import { EvalAndCorpusWorkspace } from "@/components/EvalAndCorpusWorkspace";
import { RagWorkspace } from "@/components/RagWorkspace";
import { TriageWorkspace } from "@/components/TriageWorkspace";
import { API_PROXY_PREFIX, fetchHealth } from "@/lib/api";
import type { HealthResponse, LanguageMode } from "@/lib/types";

type ActiveTab = "rag" | "triage" | "eval";

const HEALTH_RETRY_INTERVAL_MS = 5_000;
const HEALTH_MAX_ATTEMPTS = 10;

export default function HomePage() {
  const [activeTab, setActiveTab] = useState<ActiveTab>("rag");
  const [uiLang, setUiLang] = useState<LanguageMode>("en");
  const [healthState, setHealthState] = useState<"warming" | "ready" | "offline">("warming");
  const [healthInfo, setHealthInfo] = useState<HealthResponse | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pingRunIdRef = useRef(0);

  const startHealthCheck = useCallback(() => {
    if (retryTimerRef.current !== null) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }

    pingRunIdRef.current += 1;
    const runId = pingRunIdRef.current;
    setHealthState("warming");

    async function attemptPing(attempt: number) {
      let latestHealth: HealthResponse | null = null;
      try {
        latestHealth = await fetchHealth();
        if (runId !== pingRunIdRef.current) return;

        if (latestHealth.database_connected) {
          setHealthInfo(latestHealth);
          setHealthState("ready");
          return;
        }
      } catch {
        if (runId !== pingRunIdRef.current) return;
      }

      if (attempt < HEALTH_MAX_ATTEMPTS) {
        retryTimerRef.current = setTimeout(() => {
          retryTimerRef.current = null;
          void attemptPing(attempt + 1);
        }, HEALTH_RETRY_INTERVAL_MS);
        return;
      }

      if (latestHealth !== null) {
        setHealthInfo(latestHealth);
      }
      setHealthState("offline");
    }

    void attemptPing(1);
  }, []);

  useEffect(() => {
    startHealthCheck();
    return () => {
      pingRunIdRef.current += 1;
      if (retryTimerRef.current !== null) {
        clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, [startHealthCheck]);

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100">
      {/* Top Navbar */}
      <header className="sticky top-0 z-20 border-b border-slate-800/80 bg-[#090d16]/90 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3.5 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-indigo-600/20 ring-1 ring-indigo-500/40">
              <Bot className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-sm font-bold tracking-tight text-slate-100 sm:text-base">
                Enterprise RAG Ops Copilot
              </h1>
              <p className="text-[11px] text-slate-400">
                Thai–English Hybrid RAG • Pydantic v2 Ticket Triage • 25-Case Eval Gate
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {/* Render / Backend Warm-up Health Pill */}
            <button
              type="button"
              onClick={() => startHealthCheck()}
              title={`API proxied via ${API_PROXY_PREFIX}`}
              className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition ${
                healthState === "ready"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                  : healthState === "warming"
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                    : "border-rose-500/40 bg-rose-500/10 text-rose-300"
              }`}
            >
              {healthState === "warming" ? (
                <RefreshCw className="h-3 w-3 animate-spin" />
              ) : (
                <Activity className="h-3 w-3" />
              )}
              <span>
                {healthState === "ready"
                  ? `API Ready (v${healthInfo?.version ?? "0.1.0"})`
                  : healthState === "warming"
                    ? "Warming API..."
                    : "API Offline / Cold"}
              </span>
            </button>

            {/* TH / EN Toggle */}
            <button
              type="button"
              onClick={() => setUiLang((prev) => (prev === "en" ? "th" : "en"))}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-semibold text-slate-200 transition hover:border-indigo-500/50"
            >
              <Languages className="h-3.5 w-3.5 text-indigo-400" />
              <span>{uiLang === "en" ? "EN / ไทย" : "ไทย / EN"}</span>
            </button>

            <a
              href="https://github.com/ApecSinlapachai/enterprise-rag-ops-copilot"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/80 px-3 py-1 text-xs font-medium text-slate-200 transition hover:border-slate-500"
            >
              <Github className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">GitHub</span>
            </a>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="mx-auto flex max-w-6xl gap-1 px-4 sm:px-6">
          <TabButton
            active={activeTab === "rag"}
            onClick={() => setActiveTab("rag")}
            icon={<Bot className="h-4 w-4" />}
            label={uiLang === "th" ? "ถาม-ตอบ Hybrid RAG" : "Hybrid RAG Copilot"}
          />
          <TabButton
            active={activeTab === "triage"}
            onClick={() => setActiveTab("triage")}
            icon={<Ticket className="h-4 w-4" />}
            label={uiLang === "th" ? "คัดแยก Ticket Triage" : "Ticket Triage"}
          />
          <TabButton
            active={activeTab === "eval"}
            onClick={() => setActiveTab("eval")}
            icon={<BarChart3 className="h-4 w-4" />}
            label={uiLang === "th" ? "ผล Eval Scorecard และคลังเอกสาร" : "Eval Scorecard & Corpus"}
          />
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6">
        {activeTab === "rag" && <RagWorkspace uiLang={uiLang} />}
        {activeTab === "triage" && <TriageWorkspace uiLang={uiLang} />}
        {activeTab === "eval" && <EvalAndCorpusWorkspace uiLang={uiLang} />}
      </main>

      <footer className="mx-auto max-w-6xl border-t border-slate-800/80 px-4 py-5 text-center text-xs text-slate-500 sm:px-6">
        Public No-Login Portfolio Demo • Synthetic B2B SaaS Operations Corpus (`INV-2026-0091`,
        `ORG-DEMO-01`, `ERR-503`) • FastAPI + pgvector + PyThaiNLP + Tiered Gemini 3.x Routing
      </footer>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition sm:text-sm ${
        active
          ? "border-indigo-500 text-indigo-300"
          : "border-transparent text-slate-400 hover:border-slate-700 hover:text-slate-200"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}
