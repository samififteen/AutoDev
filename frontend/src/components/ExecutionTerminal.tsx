import { ArrowDownToLine, Radio, TerminalSquare } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import type { AgentLog } from "../types";
import { cn } from "../utils/format";

const levelTones: Record<string, string> = {
  error: "text-rose-300",
  warning: "text-amber-300",
  debug: "text-slate-500",
  info: "text-slate-300",
};

function timeLabel(value: string): string {
  const date = new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

export function ExecutionTerminal({
  logs,
  connected,
  running,
}: {
  logs: AgentLog[];
  connected: boolean;
  running: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (!autoScroll) return;
    const element = containerRef.current;
    if (!element) return;
    element.scrollTop = element.scrollHeight;
  }, [logs, autoScroll]);

  return (
    <div className="flex min-h-0 flex-col overflow-hidden rounded-sm border border-white/[0.09] bg-[#0b0a09]">
      <div className="flex items-center justify-between gap-3 border-b border-white/[0.06] px-3.5 py-2.5">
        <div className="flex items-center gap-2 text-[11px] text-slate-400">
          <TerminalSquare className="h-3.5 w-3.5 text-slate-500" />
          Agent output
          <span className="text-slate-600">·</span>
          <span className="text-slate-500">backend logs</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.05em]",
              connected && running
                ? "border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-300"
                : "border-white/[0.1] text-slate-500",
            )}
          >
            <Radio className={cn("h-3 w-3", connected && running && "animate-pulse-soft")} />
            {connected ? "live" : "idle"}
          </span>
          <button
            type="button"
            onClick={() => setAutoScroll((value) => !value)}
            className={cn(
              "inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] transition",
              autoScroll
                ? "bg-accent-500/[0.15] text-accent-300"
                : "text-slate-500 hover:text-slate-300",
            )}
            title="Toggle auto-scroll"
          >
            <ArrowDownToLine className="h-3 w-3" />
            auto-scroll
          </button>
        </div>
      </div>
      <div
        ref={containerRef}
        className="terminal-scroll min-h-[260px] flex-1 overflow-y-auto px-3.5 py-3 text-[11px] leading-relaxed"
        aria-live="polite"
      >
        {logs.length === 0 ? (
          <p className="py-10 text-center text-xs text-slate-600">
            No log entries yet. The agent writes every execution step here.
          </p>
        ) : (
          logs.map((log, index) => (
            <div
              key={log.id ?? `log-${index}`}
              className="flex gap-3 border-b border-white/[0.025] py-1.5 last:border-0"
            >
              <span className="shrink-0 pt-px text-[10px] text-slate-600">
                {timeLabel(log.created_at)}
              </span>
              <span
                className={cn(
                  "w-14 shrink-0 text-[10px] uppercase tracking-wide",
                  levelTones[log.level] ?? "text-slate-500",
                )}
              >
                {log.level}
              </span>
              <pre
                className={cn(
                  "mono min-w-0 flex-1 whitespace-pre-wrap break-words",
                  levelTones[log.level] ?? "text-slate-300",
                )}
              >
                {log.message}
              </pre>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
