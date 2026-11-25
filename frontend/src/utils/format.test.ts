import { describe, expect, it } from "vitest";
import { cn, formatDuration, pluralize, truncate } from "./format";

describe("format helpers", () => {
  it("formats durations across units", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(0.25)).toBe("250ms");
    expect(formatDuration(3.4)).toBe("3.4s");
    expect(formatDuration(75)).toBe("1m 15s");
    expect(formatDuration(3720)).toBe("1h 2m");
  });

  it("truncates long text without losing short text", () => {
    expect(truncate("short", 10)).toBe("short");
    expect(truncate("abcdefghij", 5)).toBe("abcd…");
  });

  it("joins class names and pluralizes", () => {
    expect(cn("a", false, null, "b")).toBe("a b");
    expect(pluralize(1, "file")).toBe("file");
    expect(pluralize(2, "file")).toBe("files");
    expect(pluralize(2, "match", "matches")).toBe("matches");
  });
});
