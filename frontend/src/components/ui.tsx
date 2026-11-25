/* eslint-disable react-refresh/only-export-components */
import {
  AlertTriangle,
  Inbox,
  Loader2,
  RotateCw,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  useEffect,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "../utils/format";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function buttonStyles(variant: Variant = "primary", size: "sm" | "md" = "md"): string {
  const variants: Record<Variant, string> = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
    danger: "btn-danger",
  };
  return cn(variants[variant], size === "sm" && "px-2.5 py-1.5 text-[9px]");
}

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: "sm" | "md";
  loading?: boolean;
  icon?: LucideIcon;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  icon: Icon,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      className={cn(buttonStyles(variant, size), className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
      ) : Icon ? (
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      ) : null}
      {children}
    </button>
  );
}

export function Card({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("panel", className)} {...props}>
      {children}
    </div>
  );
}

export function Section({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
  icon: Icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  icon?: LucideIcon;
}) {
  return (
    <section className={cn("panel", className)}>
      <div className="panel-header">
        <div className="flex min-w-0 items-center gap-2.5">
          {Icon ? <Icon className="h-3.5 w-3.5 shrink-0 text-slate-500" /> : null}
          <div className="min-w-0">
            <h2 className="panel-title">{title}</h2>
            {subtitle ? (
              <p className="mt-1 text-[10px] leading-relaxed text-slate-500">{subtitle}</p>
            ) : null}
          </div>
        </div>
        {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
      </div>
      <div className={cn("p-4", bodyClassName)}>{children}</div>
    </section>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-5 w-5 animate-spin text-accent-400", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton h-4 w-full", className)} aria-hidden="true" />;
}

export function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  action,
  className,
}: {
  icon?: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex items-start gap-4 border border-l-2 border-white/[0.09] border-l-accent-500/70 bg-ink-900/40 px-5 py-7",
        className,
      )}
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center border border-white/[0.12] bg-white/[0.02] text-slate-500">
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0">
        <p className="font-mono text-[8px] uppercase tracking-[0.16em] text-slate-600">
          Nothing on file
        </p>
        <p className="mt-1 font-display text-[22px] leading-tight text-slate-100">{title}</p>
        {description ? (
          <div className="mt-2 max-w-md text-[11px] leading-relaxed text-slate-500">
            {description}
          </div>
        ) : null}
        {action ? <div className="mt-4">{action}</div> : null}
      </div>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  className,
}: {
  message: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-start gap-3 rounded-sm border border-rose-500/25 bg-rose-500/[0.04] p-4 text-[12px] text-rose-200",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span className="leading-relaxed">{message}</span>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" icon={RotateCw} onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function Field({
  label,
  htmlFor,
  hint,
  error,
  children,
}: {
  label: string;
  htmlFor?: string;
  hint?: ReactNode;
  error?: string | null;
  children: ReactNode;
}) {
  return (
    <div>
      <label className="label" htmlFor={htmlFor}>
        {label}
      </label>
      {children}
      {error ? (
        <p className="mt-1.5 text-[11px] text-rose-300">{error}</p>
      ) : hint ? (
        <p className="mt-1.5 text-[10px] leading-relaxed text-slate-500">{hint}</p>
      ) : null}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  description?: string;
  disabled?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-sm border border-white/[0.08] bg-white/[0.01] p-3.5">
      <div>
        <p className="text-[12px] font-medium text-slate-200">{label}</p>
        {description ? (
          <p className="mt-0.5 text-[10px] leading-relaxed text-slate-500">{description}</p>
        ) : null}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 h-5 w-9 shrink-0 rounded-sm border transition disabled:opacity-50",
          checked ? "border-accent-400/60 bg-accent-500" : "border-white/[0.16] bg-ink-700",
        )}
      >
        <span
          className={cn(
            "absolute top-[3px] h-3 w-3 rounded-sm transition-all",
            checked ? "left-[19px] bg-ink-950" : "left-[3px] bg-slate-400",
          )}
        />
      </button>
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "lg",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  description?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg" | "xl";
}) {
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;
  const widths = { md: "max-w-xl", lg: "max-w-4xl", xl: "max-w-6xl" };
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/80 p-0 sm:items-center sm:p-6"
      role="dialog"
      aria-modal="true"
      aria-label={typeof title === "string" ? title : "Dialog"}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div
        className={cn(
          "flex max-h-[92vh] w-full flex-col overflow-hidden rounded-sm border border-white/[0.14] border-t-accent-500 bg-ink-850 sm:border-t-2",
          widths[size],
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-white/[0.08] px-5 py-4">
          <div className="min-w-0">
            <h2 className="font-display text-[24px] font-normal leading-tight text-slate-50">
              {title}
            </h2>
            {description ? (
              <p className="mt-1 text-[11px] leading-relaxed text-slate-500">{description}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 text-slate-500 transition hover:text-slate-200"
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">{children}</div>
        {footer ? (
          <div className="flex flex-wrap items-center justify-end gap-2 border-t border-white/[0.08] bg-ink-900 px-5 py-3.5">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function InfoRow({
  label,
  children,
  mono,
}: {
  label: string;
  children: ReactNode;
  mono?: boolean;
}) {
  return (
    <div className="flex items-start justify-between gap-6 border-b border-white/[0.05] py-2.5 last:border-0">
      <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-slate-600">
        {label}
      </span>
      <span className={cn("text-right text-[11px] text-slate-300", mono && "mono break-all")}>
        {children}
      </span>
    </div>
  );
}
