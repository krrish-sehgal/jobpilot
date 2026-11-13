import { describe, expect, it } from "vitest";
import { MockApiClient } from "./client";

describe("MockApiClient", () => {
  const api = new MockApiClient();

  it("streams a search turn in the contract's event order and is idempotent on client_message_id", async () => {
    const conv = await api.createConversation();
    const a = await api.sendMessage(conv.id, "Show me remote backend roles", "client-1");
    const b = await api.sendMessage(conv.id, "Show me remote backend roles", "client-1");
    expect(b).toEqual(a);

    const names: string[] = [];
    for await (const ev of api.streamTurn(conv.id, a.turn_id, new AbortController().signal)) names.push(ev.event);

    const firstOf = (n: string) => names.indexOf(n);
    expect(names[0]).toBe("status");
    expect(firstOf("tool_call")).toBeLessThan(firstOf("tool_result"));
    expect(firstOf("tool_result")).toBeLessThan(firstOf("token"));
    expect(firstOf("token")).toBeLessThan(firstOf("job_cards"));
    expect(names.at(-1)).toBe("done");

    const messages = await api.listMessages(conv.id);
    expect(messages.map((m) => m.role)).toEqual(["user", "assistant"]);
    expect(messages[1]!.job_cards.length).toBeGreaterThan(0);
  }, 15_000);

  it("runs a tailoring from running to ready with suggestions", async () => {
    const [resume] = await api.listResumes();
    const resumeSkills = [...(await api.getResume(resume!.id)).sections!.skills];
    const { tailoringId } = await api.createTailoring({ resume_id: resume!.id, job_id: "job-lumenfold-backend" });
    expect((await api.getTailoring(tailoringId)).status).toBe("running");
    await new Promise((r) => setTimeout(r, 3000));
    const t = await api.getTailoring(tailoringId);
    expect(t.status).toBe("ready");
    expect(t.suggestions.length).toBeGreaterThanOrEqual(5);
    expect(t.score_after).toBeGreaterThan(t.score_before);
    const reorder = t.suggestions.find((x) => x.kind === "reorder_section")!;
    expect(reorder.section).toBe("skills");
    expect(reorder.target_id).toBe("skills");
    expect(reorder.proposed.split(", ").sort()).toEqual(resumeSkills.sort());
  }, 10_000);
});
