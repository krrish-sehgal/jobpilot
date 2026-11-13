import type { ChatMessage, JobCard, StreamEvent } from "../types";
import { db, primaryResume, type MockTurn } from "./db";
import { isSearchIntent, parseQuery, rankJobs } from "./match";
import { startTailoring } from "./tailoring";
import { uuid } from "@/lib/id";
import { newId, nowIso, sleep } from "./util";

/*
  A scripted agent turn. It emits the same event sequence the real backend
  does (status -> tool_call -> tool_result -> token... -> job_cards -> done),
  with small delays so the streaming UI is visible. There is no model here:
  intent is picked with a few regexes, which is enough to demo every UI state.
*/

const ORDINALS: Record<string, number> = { first: 0, "1st": 0, second: 1, "2nd": 1, third: 2, "3rd": 2, last: -1 };

function lastCards(conversationId: string): JobCard[] {
  const msgs = db.conversations.get(conversationId)?.messages ?? [];
  return [...msgs].reverse().find((m) => m.role === "assistant" && m.job_cards.length)?.job_cards ?? [];
}

/** "tailor my resume for the second one" / "...for the Lumenfold role" -> the card the user means. */
function pickTarget(text: string, cards: JobCard[]): JobCard | undefined {
  const lower = text.toLowerCase();
  const byName = cards.find((c) => lower.includes(c.company.toLowerCase()) || lower.includes(c.title.toLowerCase()));
  if (byName) return byName;
  const ord = Object.keys(ORDINALS).find((o) => lower.includes(o));
  if (ord) return cards.at(ORDINALS[ord]!);
  return cards[0];
}

function chunk(text: string): string[] {
  return text.match(/\S+\s*/g) ?? [text];
}

export async function* runTurn(turn: MockTurn, signal: AbortSignal): AsyncGenerator<StreamEvent> {
  const text = turn.userBody;
  yield { event: "status", data: { phase: "thinking" } };
  await sleep(550, signal);

  // Demo hook: "/fail" errors the first stream so the retry UI can be seen.
  const failKey = `${turn.conversationId}:${text}`;
  if (/\/fail\b/i.test(text) && !db.failedDemo.has(failKey)) {
    db.failedDemo.add(failKey);
    yield { event: "error", data: { code: "internal", message: "The agent timed out while searching. Nothing was lost.", retryable: true } };
    return;
  }

  let reply: string;
  let cards: JobCard[] = [];
  let tailoringId: string | null = null;
  let tailoringJobId = "";

  if (/\b(tailor|rewrite my resume|improve my resume)\b/i.test(text)) {
    const target = pickTarget(text, lastCards(turn.conversationId));
    const resume = primaryResume();
    if (!target || !resume) {
      reply = !resume ? "I need a parsed resume first. Upload one on the **Resume** page and ask again." : "Ask me for some roles first, then tell me which one to tailor your resume for.";
    } else {
      const readId = uuid();
      const tailorId = uuid();
      yield { event: "status", data: { phase: "calling_tool" } };
      yield { event: "tool_call", data: { call_id: readId, name: "fetch_resume", label: "Reading your resume" } };
      await sleep(600, signal);
      yield { event: "tool_result", data: { call_id: readId, name: "fetch_resume", ok: true, summary: `Loaded ${resume.summary.file_name}` } };
      yield { event: "tool_call", data: { call_id: tailorId, name: "tailor_resume", label: `Tailoring for ${target.title} at ${target.company}` } };
      await sleep(900, signal);
      tailoringId = startTailoring(resume, { jobId: target.job_id });
      tailoringJobId = target.job_id;
      yield { event: "tool_result", data: { call_id: tailorId, name: "tailor_resume", ok: true, summary: "Started a tailoring" } };
      reply = `I've started tailoring your resume for **${target.title}** at **${target.company}**. I'll compare it to the posting, then suggest edits you can accept or reject one by one.`;
    }
  } else if (isSearchIntent(parseQuery(text))) {
    const q = parseQuery(text);
    const recallId = uuid();
    const searchId = uuid();
    yield { event: "status", data: { phase: "calling_tool" } };
    yield { event: "tool_call", data: { call_id: recallId, name: "recall_memory", label: "Checking what I know about your preferences" } };
    await sleep(500, signal);
    yield { event: "tool_result", data: { call_id: recallId, name: "recall_memory", ok: true, summary: "Recalled 2 preferences" } };
    yield { event: "tool_call", data: { call_id: searchId, name: "search_jobs", label: `Searching ${q.description}` } };
    await sleep(900, signal);
    cards = rankJobs(q);
    yield { event: "tool_result", data: { call_id: searchId, name: "search_jobs", ok: true, summary: `Found ${cards.length} matching roles` } };
    const top = cards[0]!;
    reply = [
      `I found **${cards.length} roles** that fit. The strongest is **${top.title}** at **${top.company}** (${top.match_score}% match).`,
      "",
      "Why these stood out:",
      ...cards.slice(0, 3).map((c) => `- **${c.company}**: ${c.match_reasons.join("; ").toLowerCase()}`),
      "",
      `Say "tailor my resume for the first one" and I'll start, or [open the top role](/app/jobs/${top.job_id}) to read the full posting.`,
    ].join("\n");
  } else {
    reply = [
      "Hi! I can help you in three ways:",
      "",
      "- **Find roles**: try \"remote backend roles\" or \"entry-level data jobs\"",
      "- **Explain a match**: ask why a role fits your resume",
      "- **Tailor your resume**: pick a role and I'll suggest edits",
    ].join("\n");
  }

  // Persist the reply before streaming it, so it is stored even if the client aborts mid-stream
  // (the real backend keeps generating after a disconnect; see useChatStream).
  const message: ChatMessage = { id: newId(), role: "assistant", body: reply, job_cards: cards, tailoring_id: tailoringId, created_at: nowIso() };
  const conv = db.conversations.get(turn.conversationId);
  if (conv) {
    conv.messages.push(message);
    conv.summary.last_message_preview = reply.replace(/[*\n-]+/g, " ").trim().slice(0, 90);
    conv.summary.updated_at = message.created_at;
  }

  yield { event: "status", data: { phase: "writing" } };
  for (const piece of chunk(reply)) {
    yield { event: "token", data: { text: piece } };
    await sleep(22, signal);
  }
  if (cards.length) yield { event: "job_cards", data: { cards } };
  if (tailoringId) yield { event: "tailoring_started", data: { tailoring_id: tailoringId, job_id: tailoringJobId } };
  yield { event: "done", data: { message_id: message.id } };
}
