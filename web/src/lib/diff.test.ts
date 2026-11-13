import { describe, expect, it } from "vitest";
import { diffWords } from "./diff";

const apply = (ops: ReturnType<typeof diffWords>, keep: "delete" | "insert") =>
  ops.filter((o) => o.type === "equal" || o.type === keep).map((o) => o.text).join("");

describe("diffWords", () => {
  it("returns a single equal op for identical text", () => {
    expect(diffWords("same text", "same text")).toEqual([{ type: "equal", text: "same text" }]);
  });

  it("marks replaced words as delete + insert", () => {
    const ops = diffWords("Wrote slow queries", "Optimized slow queries");
    expect(ops.find((o) => o.type === "delete")?.text).toBe("Wrote");
    expect(ops.find((o) => o.type === "insert")?.text).toBe("Optimized");
  });

  it("always reconstructs both sides exactly", () => {
    const before = "Built REST APIs for the billing module used by 40 customers.";
    const after = "Designed and shipped REST APIs for the billing module serving 40 enterprise customers.";
    const ops = diffWords(before, after);
    expect(apply(ops, "delete")).toBe(before);
    expect(apply(ops, "insert")).toBe(after);
  });

  it("handles empty input", () => {
    expect(diffWords("", "new words")).toEqual([{ type: "insert", text: "new words" }]);
    expect(diffWords("old", "")).toEqual([{ type: "delete", text: "old" }]);
  });
});
