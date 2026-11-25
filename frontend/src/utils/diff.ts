export type DiffLineType = "context" | "added" | "removed";

export interface DiffLine {
  type: DiffLineType;
  text: string;
  oldNumber: number | null;
  newNumber: number | null;
}

export interface SideBySideRow {
  left: DiffLine | null;
  right: DiffLine | null;
}

const LCS_LIMIT = 3_000_000;

export function computeLineDiff(original: string, modified: string): DiffLine[] {
  const oldLines = original ? original.split("\n") : [];
  const newLines = modified ? modified.split("\n") : [];
  const n = oldLines.length;
  const m = newLines.length;

  if (n * m > LCS_LIMIT) {
    return [
      ...oldLines.map((text, index) => ({
        type: "removed" as const,
        text,
        oldNumber: index + 1,
        newNumber: null,
      })),
      ...newLines.map((text, index) => ({
        type: "added" as const,
        text,
        oldNumber: null,
        newNumber: index + 1,
      })),
    ];
  }

  const table: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i -= 1) {
    for (let j = m - 1; j >= 0; j -= 1) {
      table[i][j] =
        oldLines[i] === newLines[j]
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }

  const lines: DiffLine[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (oldLines[i] === newLines[j]) {
      lines.push({ type: "context", text: oldLines[i], oldNumber: i + 1, newNumber: j + 1 });
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      lines.push({ type: "removed", text: oldLines[i], oldNumber: i + 1, newNumber: null });
      i += 1;
    } else {
      lines.push({ type: "added", text: newLines[j], oldNumber: null, newNumber: j + 1 });
      j += 1;
    }
  }
  while (i < n) {
    lines.push({ type: "removed", text: oldLines[i], oldNumber: i + 1, newNumber: null });
    i += 1;
  }
  while (j < m) {
    lines.push({ type: "added", text: newLines[j], oldNumber: null, newNumber: j + 1 });
    j += 1;
  }
  return lines;
}

export function toSideBySide(lines: DiffLine[]): SideBySideRow[] {
  const rows: SideBySideRow[] = [];
  let index = 0;
  while (index < lines.length) {
    const line = lines[index];
    if (line.type === "context") {
      rows.push({ left: line, right: line });
      index += 1;
      continue;
    }
    const removed: DiffLine[] = [];
    const added: DiffLine[] = [];
    while (index < lines.length && lines[index].type === "removed") {
      removed.push(lines[index]);
      index += 1;
    }
    while (index < lines.length && lines[index].type === "added") {
      added.push(lines[index]);
      index += 1;
    }
    if (!removed.length && !added.length) {
      rows.push({ left: null, right: null });
      index += 1;
      continue;
    }
    const count = Math.max(removed.length, added.length);
    for (let offset = 0; offset < count; offset += 1) {
      rows.push({ left: removed[offset] ?? null, right: added[offset] ?? null });
    }
  }
  return rows;
}

export function languageForPath(path: string): string {
  const extension = path.split(".").pop()?.toLowerCase();
  switch (extension) {
    case "py":
      return "python";
    case "ts":
    case "tsx":
      return "typescript";
    case "js":
    case "jsx":
      return "javascript";
    case "json":
      return "json";
    case "md":
      return "markdown";
    case "css":
      return "css";
    case "html":
      return "html";
    case "yml":
    case "yaml":
      return "yaml";
    default:
      return "text";
  }
}
