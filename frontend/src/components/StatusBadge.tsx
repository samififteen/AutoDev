import { cn } from "../utils/format";

const TONES: Record<string, string> = {
  completed: "border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-300",
  passed: "border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-300",
  ok: "border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-300",
  running: "border-accent-400/40 bg-accent-500/[0.07] text-accent-300",
  active: "border-accent-400/40 bg-accent-500/[0.07] text-accent-300",
  configured: "border-cyan-400/30 bg-cyan-500/[0.05] text-cyan-300",
  verified: "border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-300",
  awaiting_approval: "border-amber-400/30 bg-amber-500/[0.05] text-amber-300",
  queued: "border-sky-400/30 bg-sky-500/[0.05] text-sky-300",
  open: "border-sky-400/30 bg-sky-500/[0.05] text-sky-300",
  pending: "border-white/[0.14] bg-transparent text-slate-400",
  skipped: "border-white/[0.1] bg-transparent text-slate-500",
  cancelled: "border-white/[0.14] bg-transparent text-slate-400",
  closed: "border-white/[0.14] bg-transparent text-slate-400",
  error: "border-rose-400/30 bg-rose-500/[0.05] text-rose-300",
  failed: "border-rose-400/30 bg-rose-500/[0.05] text-rose-300",
  timeout: "border-amber-400/30 bg-amber-500/[0.05] text-amber-300",
  disabled: "border-white/[0.1] bg-transparent text-slate-500",
  unverified: "border-amber-400/30 bg-amber-500/[0.04] text-amber-300",
  merged: "border-violet-400/30 bg-violet-500/[0.05] text-violet-300",
};

const DOTS: Record<string, string> = {
  completed: "bg-emerald-400",
  passed: "bg-emerald-400",
  ok: "bg-emerald-400",
  running: "bg-accent-400",
  active: "bg-accent-400",
  configured: "bg-cyan-400",
  verified: "bg-emerald-400",
  awaiting_approval: "bg-amber-400",
  queued: "bg-sky-400",
  open: "bg-sky-400",
  failed: "bg-rose-400",
  error: "bg-rose-400",
  timeout: "bg-amber-400",
  unverified: "bg-amber-400",
  merged: "bg-violet-400",
};

export function StatusBadge({
  status,
  label,
  className,
  dot = true,
  pulse,
}: {
  status: string;
  label?: string;
  className?: string;
  dot?: boolean;
  pulse?: boolean;
}) {
  const display = label ?? status.replace(/_/g, " ");
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-1.5 py-0.5 font-mono text-[9px] font-medium uppercase tracking-[0.05em]",
        TONES[status] ?? "border-white/[0.12] bg-transparent text-slate-400",
        className,
      )}
    >
      {dot ? (
        <span
          className={cn(
            "h-1 w-1 shrink-0 rounded-[1px]",
            DOTS[status] ?? "bg-slate-500",
            (pulse ?? status === "running") && "animate-pulse-soft",
          )}
        />
      ) : null}
      {display}
    </span>
  );
}
