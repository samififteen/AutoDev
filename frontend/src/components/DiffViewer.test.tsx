import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { DiffFile } from "../types";
import { DiffViewer } from "./DiffViewer";

const file: DiffFile = {
  path: "calculator.py",
  change_type: "modified",
  additions: 1,
  deletions: 1,
  diff: "@@ -8,3 +8,3 @@\n def multiply(a, b):\n-    return a + b\n+    return a * b\n",
  original_content: "def multiply(a, b):\n    return a + b\n",
  modified_content: "def multiply(a, b):\n    return a * b\n",
};

describe("DiffViewer", () => {
  it("shows the real changed lines and switches to unified mode", async () => {
    const user = userEvent.setup();
    render(<DiffViewer files={[file]} />);

    expect(screen.getAllByText("calculator.py").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/return a \+ b/)).toBeInTheDocument();
    expect(screen.getByText(/return a \* b/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /unified/i }));
    expect(screen.getByText(/^\+\s+return a \* b$/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /split/i })).toBeInTheDocument();
  });

  it("reports when no files changed", () => {
    render(<DiffViewer files={[]} />);
    expect(screen.getByText("No file changes recorded.")).toBeInTheDocument();
  });
});
