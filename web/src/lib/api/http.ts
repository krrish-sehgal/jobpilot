import type { z } from "zod";
import { clearToken, getToken } from "@/lib/auth/token";
import type { ApiClient } from "./client";
import { ApiError, isRetryableStatus } from "./errors";
import * as s from "./schemas";
import { readSse } from "@/lib/sse";

/**
 * Real client. Everything funnels through `request`, which is the only place
 * that adds the bearer token, turns non-2xx bodies into ApiError, reacts to
 * 401, and validates the success body against its zod schema.
 */
export class HttpApiClient implements ApiClient {
  private readonly base: string;

  constructor(baseUrl: string) {
    this.base = `${baseUrl.replace(/\/+$/, "")}/api/v1`;
  }

  // ---------- plumbing ----------

  private headers(extra?: HeadersInit): Headers {
    const h = new Headers(extra);
    const token = getToken();
    if (token) h.set("Authorization", `Bearer ${token}`);
    return h;
  }

  private async raw(path: string, init: RequestInit = {}): Promise<Response> {
    let res: Response;
    try {
      res = await fetch(`${this.base}${path}`, { ...init, headers: this.headers(init.headers) });
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") throw e;
      throw new ApiError("network", "Network request failed", 0, true);
    }
    if (!res.ok) throw await this.toApiError(res);
    return res;
  }

  private async toApiError(res: Response): Promise<ApiError> {
    if (res.status === 401) clearToken(); // session is dead: let AuthProvider redirect
    const parsed = s.apiErrorBody.safeParse(await res.json().catch(() => null));
    const { code, message } = parsed.success
      ? parsed.data.error
      : { code: "internal", message: `Request failed (${res.status})` };
    return new ApiError(code, message, res.status, isRetryableStatus(res.status));
  }

  private async request<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
    const res = await this.raw(path, init);
    const parsed = schema.safeParse(await res.json().catch(() => null));
    if (!parsed.success) {
      throw new ApiError("bad_response", `Unexpected response from ${path}`, res.status);
    }
    return parsed.data;
  }

  private json(method: string, body?: unknown): RequestInit {
    return {
      method,
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    };
  }

  private async noContent(path: string, init: RequestInit): Promise<void> {
    await this.raw(path, init);
  }

  // ---------- auth ----------

  async requestCode(email: string) {
    await this.request("/auth/request-code", s.sentFlag, this.json("POST", { email }));
  }
  verifyCode(email: string, code: string) {
    return this.request("/auth/verify-code", s.authSession, this.json("POST", { email, code }));
  }
  me() {
    return this.request("/me", s.user);
  }

  // ---------- chat ----------

  listConversations() {
    return this.request("/conversations", s.conversationSummary.array());
  }
  createConversation() {
    return this.request("/conversations", s.conversationSummary, this.json("POST", {}));
  }
  listMessages(id: string) {
    return this.request(`/conversations/${id}/messages`, s.chatMessage.array());
  }
  sendMessage(id: string, body: string, clientMessageId: string) {
    return this.request(
      `/conversations/${id}/messages`,
      s.sentMessage,
      this.json("POST", { body, client_message_id: clientMessageId }),
    );
  }

  async *streamTurn(id: string, turnId: string, signal: AbortSignal) {
    const res = await this.raw(`/conversations/${id}/turns/${turnId}/stream`, {
      headers: { Accept: "text/event-stream" },
      signal,
    });
    if (!res.body) throw new ApiError("bad_response", "Stream had no body");
    for await (const msg of readSse(res.body)) {
      let data: unknown;
      try {
        data = JSON.parse(msg.data);
      } catch {
        continue; // ignore malformed frames rather than killing the whole reply
      }
      const parsed = s.streamEvent.safeParse({ event: msg.event, data });
      if (!parsed.success) continue; // unknown/newer event types are skipped, not fatal
      yield parsed.data;
      if (parsed.data.event === "done" || parsed.data.event === "error") return;
    }
  }

  // ---------- jobs ----------

  getJob(id: string) {
    return this.request(`/jobs/${id}`, s.jobDetail);
  }
  saveJob(id: string) {
    return this.noContent(`/jobs/${id}/save`, { method: "POST" });
  }
  unsaveJob(id: string) {
    return this.noContent(`/jobs/${id}/save`, { method: "DELETE" });
  }
  listSavedJobs() {
    return this.request("/saved-jobs", s.jobCard.array());
  }

  // ---------- resumes ----------

  /**
   * Uses XMLHttpRequest instead of fetch because fetch cannot report *upload*
   * progress. It's the one place we step outside `request`, so the token and
   * error mapping are repeated here on purpose.
   */
  uploadResume(file: File, onProgress: (f: number) => void, signal?: AbortSignal) {
    return new Promise<{ resumeId: string }>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", `${this.base}/resumes`);
      const token = getToken();
      if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onerror = () => reject(new ApiError("network", "Upload failed", 0, true));
      xhr.onabort = () => reject(new DOMException("Aborted", "AbortError"));
      xhr.onload = () => {
        let body: unknown = null;
        try {
          body = JSON.parse(xhr.responseText);
        } catch {
          /* handled below */
        }
        if (xhr.status === 401) clearToken();
        if (xhr.status < 200 || xhr.status >= 300) {
          const e = s.apiErrorBody.safeParse(body);
          const { code, message } = e.success ? e.data.error : { code: "internal", message: "Upload failed" };
          return reject(new ApiError(code, message, xhr.status, isRetryableStatus(xhr.status)));
        }
        const ack = s.resumeUploadAck.safeParse(body);
        if (!ack.success) return reject(new ApiError("bad_response", "Unexpected upload response"));
        resolve({ resumeId: ack.data.resume_id });
      };
      signal?.addEventListener("abort", () => xhr.abort());
      const form = new FormData();
      form.append("file", file);
      xhr.send(form);
    });
  }
  listResumes() {
    return this.request("/resumes", s.resumeSummary.array());
  }
  getResume(id: string) {
    return this.request(`/resumes/${id}`, s.resume);
  }
  makePrimary(id: string) {
    return this.noContent(`/resumes/${id}/primary`, { method: "POST" });
  }

  // ---------- tailoring ----------

  async createTailoring(input: Parameters<ApiClient["createTailoring"]>[0]) {
    const ack = await this.request("/tailorings", s.tailoringAck, this.json("POST", input));
    return { tailoringId: ack.tailoring_id };
  }
  getTailoring(id: string) {
    return this.request(`/tailorings/${id}`, s.tailoring);
  }
  submitDecisions(id: string, accepted: string[], rejected: string[]) {
    return this.request(`/tailorings/${id}/decisions`, s.tailoring, this.json("POST", { accepted, rejected }));
  }

  async exportTailoring(id: string, format: "pdf" | "docx") {
    const res = await this.raw(`/tailorings/${id}/export?format=${format}`);
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const match = /filename="?([^";]+)"?/i.exec(disposition);
    return { blob: await res.blob(), fileName: match?.[1] ?? `tailored-resume.${format}` };
  }
}
