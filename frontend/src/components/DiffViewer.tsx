import { Columns2, Download, FileCode2, ListTree } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { DiffFile } from "../types";
import { computeLineDiff, toSideBySide } from "../utils/diff";
import { cn, pluralize } from "../utils/format";
import { Button } from "./ui";

const typeTone: Record<string, string> = {
  added: "text-emerald-300 bg-emerald-500/10 border-emerald-400/20",
  modified: "text-amber-300 bg-amber-500/10 border-amber-400/20",
  deleted: "text-rose-300 bg-rose-500/10 border-rose-400/20",
};

function UnifiedView({ diff }: { diff: string }) {
  const lines = diff.split("\n").filter((line) => line && !line.startsWith("\\"));
  return (
    <div className="min-h-[200px] overflow-auto rounded-b-sm bg-[#0b0a09]">
      <pre className="mono min-w-max py-2 text-[11px] leading-[1.7]">
        {lines.map((line, index) => {
          const added = line.startsWith("+") && !line.startsWith("+++");
          const removed = line.startsWith("-") && !line.startsWith("---");
          const header = line.startsWith("@@") || line.startsWith("diff ") || line.startsWith("index ");
          return (
            <div
              key={index}
              className={cn(
                "px-4",
                added && "bg-emerald-500/[0.09] text-emerald-200",
                removed && "bg-rose-500/[0.09] text-rose-200",
                header && "text-indigo-300",
                !added && !removed && !header && "text-slate-400",
              )}
            >
              {line}
            </div>
          );
        })}
      </pre>
    </div>
  );
}

export function DiffViewer({
  files,
  initialPath,
  onDownload,
  downloading,
}: {
  files: DiffFile[];
  initialPath?: string | null;
  onDownload?: () => void;
  downloading?: boolean;
}) {
  const [selected, setSelected] = useState(initialPath ?? files[0]?.path ?? "");
  const [mode, setMode] = useState<"split" | "unified">("split");

  useEffect(() => {
    if (files.length && !files.some((file) => file.path === selected)) {
      setSelected(files[0].path);
    }
  }, [files, selected]);

  const file = files.find((item) => item.path === selected) ?? files[0];
  const rows = useMemo(() => {
    if (!file) return [];
    return toSideBySide(computeLineDiff(file.original_content ?? "", file.modified_content ?? ""));
  }, [file]);

  if (!files.length) {
    return (
      <p className="py-10 text-center text-sm text-slate-500">No file changes recorded.</p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-white/[0.07]">
      <div className="flex flex-col gap-2 border-b border-white/[0.06] bg-ink-900/70 p-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-1">
          {files.map((item) => (
            <button
              key={item.path}
              type="button"
              onClick={() => setSelected(item.path)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] transition",
                item.path === file?.path
                  ? "bg-accent-500/[0.15] text-accent-200"
                  : "text-slate-400 hover:bg-white/[0.04] hover:text-slate-200",
              )}
              title={item.path}
            >
              <FileCode2 className="h-3 w-3 shrink-0" />
              <span className="max-w-[220px] truncate">{item.path.split("/").pop()}</span>
              <span className="text-emerald-400">+{item.additions}</span>
              <span className="text-rose-400">-{item.deletions}</span>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            icon={mode === "split" ? ListTree : Columns2}
            onClick={() => setMode(mode === "split" ? "unified" : "split")}
          >
            {mode === "split" ? "Unified" : "Split"}
          </Button>
          {onDownload ? (
            <Button
              variant="secondary"
              size="sm"
              icon={Download}
              loading={downloading}
              onClick={onDownload}
            >
              Patch
            </Button>
          ) : null}
        </div>
      </div>

      {file ? (
        <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] bg-white/[0.015] px-3 py-2">
          <span className="mono break-all text-[11px] text-slate-300">{file.path}</span>
          <span
            className={cn(
              "rounded-sm border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.05em]",
              typeTone[file.change_type] ?? "border-white/10 text-slate-400",
            )}
          >
            {file.change_type}
          </span>
          <span className="ml-auto text-[10px] text-slate-500">
            +{file.additions} / -{file.deletions} across {pluralize(file.additions + file.deletions, "line change")}
          </span>
        </div>
      ) : null}

      {mode === "split" ? (
        <div className="max-h-[55vh] overflow-auto bg-[#0b0a09]">
          <table className="w-full border-collapse">
            <tbody className="mono text-[11px] leading-[1.75]">
              {rows.map((row, index) => (
                <tr key={index}>
                  <td className="w-10 select-none border-r border-white/[0.05] px-2 text-right align-top text-[10px] text-slate-600">
                    {row.left?.oldNumber ?? ""}
                  </td>
                  <td
                    className={cn(
                      "w-1/2 whitespace-pre-wrap break-all px-3 align-top text-slate-300",
                      row.left?.type === "removed" && "bg-rose-500/[0.08] text-rose-200",
                    )}
                  >
                    {row.left?.text ?? "\u00a0"}
                  </td>
                  <td className="w-10 select-none border-l border-r border-white/[0.05] px-2 text-right align-top text-[10px] text-slate-600">
                    {row.right?.newNumber ?? ""}
                  </td>
                  <td
                    className={cn(
                      "w-1/2 whitespace-pre-wrap break-all px-3 align-top text-slate-300",
                      row.right?.type === "added" && "bg-emerald-500/[0.08] text-emerald-200",
                    )}
                  >
                    {row.right?.text ?? "\u00a0"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <UnifiedView diff={file?.diff ?? ""} />
      )}
    </div>
  );
}
