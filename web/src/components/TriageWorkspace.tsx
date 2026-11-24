"use client";

import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Coins,
  Send,
  Sparkles,
  Tag,
  Timer,
  UserCheck,
} from "lucide-react";

import { ApiError, submitTriage } from "@/lib/api";
import type { LanguageMode, TriageTicketResponse } from "@/lib/types";

interface SampleTicket {
  id: string;
  labelTh: string;
  labelEn: string;
  channel: "web_demo" | "line" | "email" | "api";
  message: string;
}

const SAMPLE_TICKETS: SampleTicket[] = [
  {
    id: "th-billing",
    labelTh: "TH: ตัดบัตรซ้ำ INV-2026-0091",
    labelEn: "TH: Double Charge INV-2026-0091",
    channel: "line",
    message:
      "รบกวนตรวจสอบใบแจ้งหนี้ INV-2026-0091 ของ ORG-DEMO-01 ถูกตัดบัตรซ้ำ 2 รอบยอด 12,500 บาท ต้องการขอคืนเงินด่วนครับ",
  },
  {
    id: "en-p0",
    labelTh: "EN: เหตุขัดข้อง P0 (ERR-503)",
    labelEn: "EN: Production ERR-503 Outage",
    channel: "email",
    message:
      "URGENT P0: Production API gateway returning ERR-503 for all Enterprise SSO logins at ORG-DEMO-01 since 09:15 UTC. Customer checkout is completely down!",
  },
  {
    id: "mixed-access",
    labelTh: "Mixed: ERR-AUTH-403 หลังต่ออายุ",
    labelEn: "Mixed: ERR-AUTH-403 After Renewal",
    channel: "web_demo",
    message:
      "ทีมงาน ORG-DEMO-01 เจอ ERR-AUTH-403 after renewing SKU-ENT-ANNUAL. ช่วย unlock SAML SSO ให้หน่อยค่ะ",
  },
];

const PRIORITY_BADGE: Record<TriageTicketResponse["priority"], string> = {
  P0: "border-rose-500/50 bg-rose-500/15 text-rose-200",
  P1: "border-amber-500/50 bg-amber-500/15 text-amber-200",
  P2: "border-cyan-500/50 bg-cyan-500/15 text-cyan-200",
  P3: "border-slate-600 bg-slate-800 text-slate-300",
};

export function TriageWorkspace({ uiLang }: { uiLang: LanguageMode }) {
  const [message, setMessage] = useState(SAMPLE_TICKETS[0].message);
  const [channel, setChannel] = useState<"web_demo" | "line" | "email" | "api">("web_demo");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TriageTicketResponse | null>(null);

  async function handleTriage(msg: string, ch: "web_demo" | "line" | "email" | "api") {
    const trimmed = msg.trim();
    if (trimmed.length < 5) return;
    setLoading(true);
    setError(null);
    try {
      const res = await submitTriage({ message: trimmed, source_channel: ch });
      setResult(res);
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError(
          `Rate limit reached (HTTP 429). Please retry in ${err.retryAfterSeconds ?? 60}s.`,
        );
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Unexpected error while running ticket triage.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              {uiLang === "th"
                ? "คัดแยก Support Ticket อัตโนมัติ (Pydantic v2 Schema)"
                : "Structured Support Ticket Triage (Pydantic v2 Contract)"}
            </h2>
            <p className="text-xs text-slate-400">
              {uiLang === "th"
                ? "สกัด Category, Priority, Team, Entities และบันทึกลง PostgreSQL พร้อม Retry + Fallback"
                : "Extracts category, urgency (StrictInt 1-5), team routing, and synthetic entities with tenacity retry & deterministic fallback."}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <label htmlFor="triage-channel" className="text-xs text-slate-400">
              Channel:
            </label>
            <select
              id="triage-channel"
              value={channel}
              onChange={(e) =>
                setChannel(e.target.value as "web_demo" | "line" | "email" | "api")
              }
              className="rounded-lg border border-slate-700 bg-slate-950 px-2.5 py-1 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
            >
              <option value="web_demo">web_demo</option>
              <option value="line">line</option>
              <option value="email">email</option>
              <option value="api">api</option>
            </select>
          </div>
        </div>

        <div className="mb-3 flex flex-wrap gap-2">
          {SAMPLE_TICKETS.map((sample) => (
            <button
              key={sample.id}
              type="button"
              disabled={loading}
              onClick={() => {
                setMessage(sample.message);
                setChannel(sample.channel);
                void handleTriage(sample.message, sample.channel);
              }}
              className="rounded-full border border-slate-700 bg-slate-800/70 px-3 py-1 text-xs font-medium text-slate-200 transition hover:border-indigo-500/50 hover:bg-slate-800 disabled:opacity-50"
            >
              {uiLang === "th" ? sample.labelTh : sample.labelEn}
            </button>
          ))}
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            void handleTriage(message, channel);
          }}
          className="space-y-3"
        >
          <div className="relative">
            <textarea
              rows={4}
              maxLength={1500}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder={
                uiLang === "th"
                  ? "วางข้อความ Ticket จากลูกค้า (5–1,500 ตัวอักษร)..."
                  : "Paste an inbound customer support ticket (5–1,500 chars)..."
              }
              className="w-full resize-none rounded-xl border border-slate-700 bg-slate-950/90 p-3.5 text-sm text-slate-100 placeholder-slate-500 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            />
            <span className="absolute bottom-2.5 right-3 font-mono text-[11px] text-slate-500">
              {message.length}/1500
            </span>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={loading || message.trim().length < 5}
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-indigo-600/20 transition hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Sparkles className="h-4 w-4 animate-spin" />
                  <span>{uiLang === "th" ? "กำลังวิเคราะห์..." : "Classifying Ticket..."}</span>
                </>
              ) : (
                <>
                  <Send className="h-4 w-4" />
                  <span>{uiLang === "th" ? "คัดแยก Ticket" : "Classify & Persist"}</span>
                </>
              )}
            </button>
          </div>
        </form>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-xs text-rose-200">
            {error}
          </div>
        )}
      </section>

      {result && (
        <section className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900/70 p-5 shadow-xl">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded-full border px-3 py-0.5 font-mono text-xs font-bold ${PRIORITY_BADGE[result.priority]}`}
              >
                {result.priority} (Urgency {result.urgency_score}/5)
              </span>
              <span className="rounded-full border border-indigo-500/40 bg-indigo-500/10 px-3 py-0.5 font-mono text-xs text-indigo-300">
                {result.category}
              </span>
              <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-3 py-0.5 font-mono text-xs text-emerald-300">
                team: {result.suggested_team}
              </span>
              {result.requires_human_review && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/40 bg-amber-500/10 px-2.5 py-0.5 text-xs text-amber-200">
                  <UserCheck className="h-3.5 w-3.5" />
                  Human Review
                </span>
              )}
            </div>
            <span className="font-mono text-[11px] text-slate-500">{result.request_id}</span>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Summary
              </h3>
              <p className="mt-1.5 text-sm text-slate-100">{result.summary}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                Suggested Action
              </h3>
              <p className="mt-1.5 text-sm text-slate-100">{result.suggested_action}</p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 text-xs text-slate-400">
              <Tag className="h-3.5 w-3.5" />
              Extracted Entities:
            </span>
            {Object.keys(result.extracted_entities).length === 0 ? (
              <span className="text-xs text-slate-500">None</span>
            ) : (
              Object.entries(result.extracted_entities).map(([k, v]) => (
                <span
                  key={k}
                  className="rounded-lg border border-slate-700 bg-slate-800/80 px-2.5 py-1 font-mono text-xs text-slate-200"
                >
                  {k}: <span className="text-cyan-300">{v}</span>
                </span>
              ))
            )}
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-800 pt-3 text-xs text-slate-400">
            <div className="flex flex-wrap items-center gap-4 font-mono">
              <span className="inline-flex items-center gap-1 text-emerald-300">
                {result.validation_status === "pydantic_passed" ? (
                  <CheckCircle2 className="h-3.5 w-3.5" />
                ) : (
                  <AlertCircle className="h-3.5 w-3.5 text-amber-300" />
                )}
                {result.validation_status}
              </span>
              <span>lang: {result.language_detected}</span>
              <span>sentiment: {result.sentiment}</span>
            </div>
            <div className="flex items-center gap-4 font-mono">
              <span className="inline-flex items-center gap-1">
                <Timer className="h-3.5 w-3.5 text-indigo-400" />
                {result.latency_ms} ms
              </span>
              <span className="inline-flex items-center gap-1 text-emerald-300">
                <Coins className="h-3.5 w-3.5" />${result.estimated_cost_usd.toFixed(6)}
              </span>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
