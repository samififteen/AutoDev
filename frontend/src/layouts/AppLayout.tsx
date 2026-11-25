import {
  Bell,
  CheckCircle2,
  FolderGit2,
  Menu,
  PanelLeftClose,
  RefreshCw,
  Settings,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { StatusBadge } from "../components/StatusBadge";
import { useApiQuery } from "../hooks/useApiQuery";
import { api } from "../services/api";
import { cn } from "../utils/format";

const navItems = [
  { to: "/", label: "Overview", code: "01", end: true },
  { to: "/repositories", label: "Repositories", code: "02" },
  { to: "/tasks", label: "Issues & Tasks", code: "03" },
  { to: "/workspace", label: "Agent Workspace", code: "04" },
  { to: "/pull-requests", label: "Pull Requests", code: "05" },
  { to: "/history", label: "Execution History", code: "06" },
  { to: "/settings", label: "Settings", code: "07" },
];

const COLLAPSE_KEY = "autodev.sidebarCollapsed";

export default function AppLayout() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(COLLAPSE_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  const status = useApiQuery(() => api.systemStatus(), []);
  const health = useApiQuery(() => api.health(), []);
  const notifications = useApiQuery(() => api.executions({ page_size: 5 }), []);

  useEffect(() => {
    setMobileOpen(false);
    setNotificationsOpen(false);
    setProfileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    try {
      localStorage.setItem(COLLAPSE_KEY, String(collapsed));
    } catch {
      // ignore storage failures
    }
  }, [collapsed]);

  useEffect(() => {
    const handler = (event: MouseEvent) => {
      const target = event.target as Node;
      if (notificationsRef.current && !notificationsRef.current.contains(target)) {
        setNotificationsOpen(false);
      }
      if (profileRef.current && !profileRef.current.contains(target)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const github = status.data?.github;
  const demoMode = health.data?.demo_mode ?? false;
  const current =
    [...navItems]
      .reverse()
      .find((item) =>
        item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
      ) ?? navItems[0];

  return (
    <div className="flex min-h-screen">
      {mobileOpen ? (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-40 bg-black/70 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      ) : null}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-white/[0.08] bg-ink-900 transition-all duration-150 md:sticky md:top-0 md:z-20 md:h-screen md:translate-x-0",
          collapsed ? "md:w-[64px]" : "md:w-[232px]",
          "w-[232px]",
          mobileOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0",
        )}
      >
        <div className="flex h-14 items-center justify-between gap-2 border-b border-white/[0.08] px-4">
          <Link to="/" className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center border border-accent-500/60 bg-accent-500/[0.08] font-mono text-[10px] font-semibold tracking-[-0.04em] text-accent-300">
              AD
            </span>
            <span className={cn("min-w-0", collapsed && "md:hidden")}>
              <span className="block truncate font-display text-[19px] leading-none text-slate-50">
                AutoDev
              </span>
              <span className="mt-1 block truncate font-mono text-[7px] uppercase tracking-[0.18em] text-slate-600">
                agent console
              </span>
            </span>
          </Link>
          <button
            type="button"
            className="p-1.5 text-slate-500 hover:text-slate-200 md:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto py-4" aria-label="Main navigation">
          <p
            className={cn(
              "mb-3 px-4 font-mono text-[7px] uppercase tracking-[0.2em] text-slate-600",
              collapsed && "md:hidden",
            )}
          >
            Navigation
          </p>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              title={collapsed ? item.label : undefined}
              className={({ isActive }) =>
                cn(
                  "group relative flex items-center gap-3 border-l-2 py-2.5 pl-4 pr-3 transition",
                  isActive
                    ? "border-accent-500 bg-white/[0.035] text-slate-100"
                    : "border-transparent text-slate-500 hover:border-white/20 hover:bg-white/[0.02] hover:text-slate-300",
                  collapsed && "md:justify-center md:border-l-0 md:px-0",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={cn(
                      "mono text-[9px] tracking-[0.04em]",
                      isActive ? "text-accent-400" : "text-slate-600",
                    )}
                  >
                    {item.code}
                  </span>
                  <span className={cn("truncate text-[12px]", collapsed && "md:hidden")}>
                    {item.label}
                  </span>
                </>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/[0.08] px-4 py-4">
          <div className={cn("space-y-1.5", collapsed && "md:hidden")}>
            <div className="flex items-center justify-between font-mono text-[8px] uppercase tracking-[0.08em]">
              <span className="text-slate-600">mode</span>
              <span className="text-accent-400">{demoMode ? "demo" : "live"}</span>
            </div>
            <div className="flex items-center justify-between font-mono text-[8px] uppercase tracking-[0.08em]">
              <span className="text-slate-600">api</span>
              <span className={status.data ? "text-emerald-400" : "text-rose-400"}>
                {status.data ? "online" : status.error ? "offline" : "checking"}
              </span>
            </div>
            <div className="flex items-center justify-between font-mono text-[8px] uppercase tracking-[0.08em]">
              <span className="text-slate-600">rev</span>
              <span className="text-slate-400">{health.data?.version ?? "—"}</span>
            </div>
          </div>
          <div className={cn("hidden items-center justify-center", collapsed && "md:flex")}>
            <span
              className={cn(
                "h-1.5 w-1.5",
                status.data ? "bg-emerald-400" : "bg-rose-400",
              )}
            />
          </div>
          <button
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            className={cn(
              "mt-4 hidden w-full items-center gap-2 border-t border-white/[0.07] pt-3 font-mono text-[8px] uppercase tracking-[0.08em] text-slate-600 transition hover:text-slate-300 md:flex",
              collapsed && "justify-center",
            )}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <Menu className="h-3.5 w-3.5" />
            ) : (
              <>
                <PanelLeftClose className="h-3.5 w-3.5" />
                collapse
              </>
            )}
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-white/[0.08] bg-ink-950/95 px-4 sm:px-6">
          <button
            type="button"
            className="p-2 text-slate-400 hover:text-slate-100 md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open navigation"
          >
            <Menu className="h-5 w-5" />
          </button>
          <div className="flex min-w-0 items-center gap-2 font-mono text-[9px] uppercase tracking-[0.12em]">
            <span className="hidden text-slate-600 sm:inline">AutoDev</span>
            <span className="hidden text-slate-700 sm:inline">/</span>
            <span className="truncate text-slate-300">{current.label}</span>
            <span className="ml-1 hidden border border-white/[0.1] px-1.5 py-0.5 text-[7px] text-slate-500 sm:inline">
              {demoMode ? "demo" : "live"}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <Link
              to="/settings"
              className="hidden items-center gap-2 border border-white/[0.1] px-2.5 py-1.5 font-mono text-[8px] uppercase tracking-[0.08em] text-slate-500 transition hover:border-white/[0.22] hover:text-slate-300 sm:flex"
            >
              <span
                className={cn(
                  "h-1 w-1",
                  github?.status === "ok" ? "bg-emerald-400" : "bg-slate-600",
                )}
              />
              GitHub · {github?.status ?? "unknown"}
            </Link>

            <div className="relative" ref={notificationsRef}>
              <button
                type="button"
                className="relative p-2 text-slate-500 transition hover:text-slate-200"
                onClick={() => setNotificationsOpen((value) => !value)}
                aria-label="Notifications"
                aria-expanded={notificationsOpen}
              >
                <Bell className="h-4 w-4" />
                {notifications.data &&
                notifications.data.items.some((item) => item.status === "failed") ? (
                  <span className="absolute right-1.5 top-1.5 h-1 w-1 bg-rose-400" />
                ) : null}
              </button>
              {notificationsOpen ? (
                <div className="absolute right-0 top-10 w-[min(92vw,360px)] animate-fade-in border border-white/[0.12] bg-ink-850">
                  <div className="flex items-center justify-between border-b border-white/[0.08] px-4 py-3">
                    <p className="font-mono text-[9px] uppercase tracking-[0.12em] text-slate-400">
                      Recent activity
                    </p>
                    <Link
                      to="/history"
                      className="font-mono text-[9px] uppercase tracking-[0.08em] text-accent-400 hover:text-accent-300"
                    >
                      View all
                    </Link>
                  </div>
                  <div className="max-h-80 overflow-y-auto">
                    {notifications.data?.items.length ? (
                      notifications.data.items.map((item) => (
                        <Link
                          key={item.id}
                          to={`/workspace/${item.id}`}
                          className="flex items-start gap-3 border-b border-white/[0.05] px-4 py-3 transition last:border-0 hover:bg-white/[0.025]"
                        >
                          <StatusBadge status={item.status} dot={false} />
                          <div className="min-w-0">
                            <p className="truncate text-[12px] text-slate-200">
                              {item.task?.title ?? `Execution #${item.id}`}
                            </p>
                            <p className="mt-0.5 truncate font-mono text-[8px] uppercase tracking-[0.04em] text-slate-600">
                              {item.task?.repository?.full_name ?? "unknown repository"} ·{" "}
                              {item.current_stage.replace(/_/g, " ")}
                            </p>
                          </div>
                        </Link>
                      ))
                    ) : (
                      <p className="px-4 py-8 text-center font-mono text-[9px] uppercase tracking-[0.06em] text-slate-600">
                        No agent activity yet
                      </p>
                    )}
                  </div>
                </div>
              ) : null}
            </div>

            <Link
              to="/settings"
              className="p-2 text-slate-500 transition hover:text-slate-200"
              aria-label="Settings"
            >
              <Settings className="h-4 w-4" />
            </Link>

            <div className="relative" ref={profileRef}>
              <button
                type="button"
                onClick={() => setProfileOpen((value) => !value)}
                className="flex items-center gap-1.5 border border-white/[0.1] px-2 py-1.5 font-mono text-[8px] uppercase tracking-[0.08em] text-slate-500 transition hover:border-white/[0.22] hover:text-slate-300"
                aria-label="Local environment menu"
                aria-expanded={profileOpen}
              >
                <span className="h-1 w-1 bg-accent-500" />
                local
              </button>
              {profileOpen ? (
                <div className="absolute right-0 top-10 w-64 animate-fade-in border border-white/[0.12] bg-ink-850">
                  <div className="border-b border-white/[0.08] px-4 py-3">
                    <p className="text-[13px] font-medium text-slate-100">Local developer</p>
                    <p className="mt-0.5 font-mono text-[8px] uppercase tracking-[0.08em] text-slate-600">
                      AutoDev {health.data ? `v${health.data.version}` : ""}
                    </p>
                  </div>
                  <Link
                    to="/settings"
                    className="flex items-center gap-2 px-4 py-2.5 font-mono text-[9px] uppercase tracking-[0.06em] text-slate-400 hover:bg-white/[0.03] hover:text-slate-200"
                  >
                    <Settings className="h-3.5 w-3.5" /> Settings
                  </Link>
                  <Link
                    to="/repositories"
                    className="flex items-center gap-2 px-4 py-2.5 font-mono text-[9px] uppercase tracking-[0.06em] text-slate-400 hover:bg-white/[0.03] hover:text-slate-200"
                  >
                    <FolderGit2 className="h-3.5 w-3.5" /> Repository access
                  </Link>
                  <div className="flex items-center gap-2 border-t border-white/[0.08] px-4 py-2.5 font-mono text-[8px] uppercase tracking-[0.04em] text-slate-600">
                    {status.data?.database.status === "ok" ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5" />
                    )}
                    database {status.data?.database.status ?? "checking"}
                  </div>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1520px] flex-1 px-5 py-8 sm:px-7 lg:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
