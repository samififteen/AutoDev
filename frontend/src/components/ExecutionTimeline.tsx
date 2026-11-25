import { Check, Circle, Loader2, Minus, X } from "lucide-react";
import type { TimelineStep } from "../types";
import { cn } from "../utils/format";

const styles = {
  completed: {
    icon: Check,
    node: "border-emerald-400/40 bg-emerald-500/[0.08] text-emerald-300",
    line: "bg-emerald-400/20",
    label: "text-slate-300",
  },
  active: {
    icon: Loader2,
    node: "border-accent-400/60 bg-accent-500/[0.1] text-accent-300",
    line: "bg-white/[0.08]",
    label: "font-medium text-accent-200",
  },
  pending: {
    icon: Circle,
    node: "border-white/[0.1] bg-transparent text-slate-600",
    line: "bg-white/[0.06]",
    label: "text-slate-500",
  },
  skipped: {
    icon: Minus,
    node: "border-white/[0.08] bg-transparent text-slate-600",
    line: "bg-white/[0.06]",
    label: "text-slate-600",
  },
  failed: {
    icon: X,
    node: "border-rose-400/40 bg-rose-500/[0.08] text-rose-300",
    line: "bg-white/[0.06]",
    label: "text-rose-200",
  },
};

export function ExecutionTimeline({ steps }: { steps: TimelineStep[] }) {
  return (
    <ol className="space-y-0">
      {steps.map((step, index) => {
        const style = styles[step.status];
        const Icon = style.icon;
        return (
          <li key={step.key} className="flex gap-3">
            <div className="flex flex-col items-center">
              <span
                className={cn(
                  "mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-sm border",
                  style.node,
                )}
              >
                <Icon
                  className={cn("h-2.5 w-2.5", step.status === "active" && "animate-spin")}
                />
              </span>
              {index < steps.length - 1 ? (
                <span className={cn("my-1 w-px flex-1", style.line)} />
              ) : null}
            </div>
            <div
              className={cn(
                "flex min-w-0 flex-1 gap-3 pb-4 text-[12px] leading-5",
                style.label,
              )}
            >
              <span className="mono shrink-0 text-[9px] leading-5 text-slate-600">
                {String(index + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0">{step.label}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
