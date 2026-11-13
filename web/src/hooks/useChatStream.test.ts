import { describe, expect, it } from "vitest";
import { applyEvent, initialStreamState } from "./useChatStream";
import type { StreamEvent } from "@/lib/api/types";

const run = (events: StreamEvent[]) => events.reduce(applyEvent, initialStreamState);

describe("applyEvent", () => {
  it("tracks a tool from running to finished and accumulates tokens", () => {
    const s = run([
      { event: "tool_call", data: { call_id: "c1", name: "search_jobs", label: "Searching remote backend roles" } },
      { event: "tool_result", data: { call_id: "c1", name: "search_jobs", ok: true, summary: "Found 6 matching roles" } },
      { event: "token", data: { text: "Hello " } },
      { event: "token", data: { text: "there" } },
    ]);
    expect(s.tools).toEqual([{ callId: "c1", name: "search_jobs", label: "Searching remote backend roles", status: "ok", summary: "Found 6 matching roles" }]);
    expect(s.text).toBe("Hello there");
  });

  it("records an error event as a retryable failure", () => {
    const s = run([{ event: "error", data: { code: "internal", message: "boom", retryable: true } }]);
    expect(s.status).toBe("error");
    expect(s.error).toEqual({ message: "boom", retryable: true });
  });
});
