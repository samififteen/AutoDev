import type { LucideIcon } from "lucide-react";
import { cn } from "../utils/format";

const RULES = {
  indigo: "bg-accent-500",
  emerald: "bg-emerald-500",
  rose: "bg-rose-500",
  amber: "bg-amber-500",
  violet: "bg-violet-500",
  slate: "bg-slate-600",
};

export function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "indigo",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  tone?: keyof typeof RULES;
}) {
  return (
    <div className="panel relative overflow-hidden p-4 pt-5">
      <span className={cn("absolute left-0 top-0 h-[2px] w-10", RULES[tone])} />
      <div className="flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.1em] text-slate-500">
        <Icon className="h-3 w-3 text-slate-600" />
        <span className="truncate">{label}</span>
      </div>
      <p className="mt-4 font-mono text-[27px] leading-none tracking-[-0.04em] text-slate-50">
        {value}
      </p>
      {hint ? <p className="mt-2 truncate text-[10px] text-slate-500">{hint}</p> : null}
    </div>
  );
}
