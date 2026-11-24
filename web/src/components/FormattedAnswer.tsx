"use client";

import React from "react";

interface FormattedAnswerProps {
  text: string;
}

/**
 * Render lightweight Markdown inline tokens (`**bold**`, `` `code` ``)
 * as pure React nodes without `dangerouslySetInnerHTML`.
 */
function renderInline(line: string, keyPrefix: string): React.ReactNode[] {
  const tokens: React.ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let idx = 0;

  while ((match = pattern.exec(line)) !== null) {
    if (match.index > lastIndex) {
      tokens.push(line.slice(lastIndex, match.index));
    }
    const raw = match[0];
    if (raw.startsWith("**") && raw.endsWith("**")) {
      tokens.push(
        <strong key={`${keyPrefix}-b-${idx}`} className="font-semibold text-white">
          {raw.slice(2, -2)}
        </strong>,
      );
    } else if (raw.startsWith("`") && raw.endsWith("`")) {
      tokens.push(
        <code
          key={`${keyPrefix}-c-${idx}`}
          className="rounded bg-slate-800/90 px-1.5 py-0.5 font-mono text-[12px] text-indigo-300"
        >
          {raw.slice(1, -1)}
        </code>,
      );
    }
    lastIndex = match.index + raw.length;
    idx += 1;
  }

  if (lastIndex < line.length) {
    tokens.push(line.slice(lastIndex));
  }

  return tokens;
}

export function FormattedAnswer({ text }: FormattedAnswerProps) {
  const lines = text.split(/\r?\n/);

  return (
    <div className="space-y-2 text-sm leading-relaxed text-slate-100">
      {lines.map((rawLine, index) => {
        const line = rawLine.trim();
        if (!line) {
          return <div key={`sp-${index}`} className="h-1" />;
        }

        const headingMatch = /^(#{1,3})\s+(.*)$/.exec(line);
        if (headingMatch) {
          return (
            <h4 key={`h-${index}`} className="pt-1 text-sm font-semibold text-indigo-200">
              {renderInline(headingMatch[2], `h-${index}`)}
            </h4>
          );
        }

        const bulletMatch = /^([-*•])\s+(.*)$/.exec(line);
        if (bulletMatch) {
          return (
            <div key={`li-${index}`} className="flex items-start gap-2 pl-1">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-indigo-400" />
              <span className="flex-1">{renderInline(bulletMatch[2], `li-${index}`)}</span>
            </div>
          );
        }

        const numberedMatch = /^(\d+\.)\s+(.*)$/.exec(line);
        if (numberedMatch) {
          return (
            <div key={`ol-${index}`} className="flex items-start gap-2 pl-1">
              <span className="shrink-0 font-mono text-xs font-semibold text-indigo-300">
                {numberedMatch[1]}
              </span>
              <span className="flex-1">{renderInline(numberedMatch[2], `ol-${index}`)}</span>
            </div>
          );
        }

        return <p key={`p-${index}`}>{renderInline(line, `p-${index}`)}</p>;
      })}
    </div>
  );
}
