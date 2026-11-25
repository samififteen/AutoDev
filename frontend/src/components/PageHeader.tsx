import type { ReactNode } from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-5 border-b border-white/[0.09] pb-6 sm:flex-row sm:items-end">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-2 flex items-center gap-2 font-mono text-[9px] font-medium uppercase tracking-[0.2em] text-accent-400">
            <span className="inline-block h-px w-5 bg-accent-500" />
            {eyebrow}
          </p>
        ) : null}
        <h1 className="font-display text-[34px] font-normal leading-[1.02] tracking-[-0.01em] text-slate-50 sm:text-[42px]">
          {title}
        </h1>
        {description ? (
          <p className="mt-2.5 max-w-2xl text-[13px] leading-relaxed text-slate-400">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}
