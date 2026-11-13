"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { api } from "@/lib/api";
import { describeError, isApiError } from "@/lib/api/errors";
import type { ChatMessage, JobCard, StreamEvent, ToolName } from "@/lib/api/types";
import { uuid } from "@/lib/id";

export interface ToolActivity {
  callId: string;
  name: ToolName;
  label: string;
  status: "running" | "ok" | "failed";
  summary?: string;
}

export interface StreamState {
  /** idle: nothing in flight. active: request sent / streaming. error: turn failed. */
  status: "idle" | "active" | "error";
  agentPhase: "thinking" | "calling_tool" | "writing" | null;
  tools: ToolActivity[];
  text: string;
  cards: JobCard[];
  tailoring: { tailoringId: string; jobId: string } | null;
  messageId: string | null;
  error: { message: string; retryable: boolean } | null;
}

export const initialStreamState: StreamState = {
  status: "idle", agentPhase: null, tools: [], text: "", cards: [], tailoring: null, messageId: null, error: null,
};

type Action = { type: "start" } | { type: "reset" } | { type: "fail"; message: string; retryable: boolean } | { type: "event"; event: StreamEvent };

/** Folds one SSE event into the in-progress reply. Pure, so it is easy to test and to reason about. */
export function applyEvent(state: StreamState, ev: StreamEvent): StreamState {
  switch (ev.event) {
    case "status": return { ...state, agentPhase: ev.data.phase };
    case "tool_call": {
      // A tool started: add it to the activity list as "running".
      const started: ToolActivity = { callId: ev.data.call_id, name: ev.data.name, label: ev.data.label, status: "running" };
      return { ...state, tools: [...state.tools, started] };
    }
    case "tool_result": {
      // The matching tool finished: flip its status and attach the one-line summary.
      const status = ev.data.ok ? "ok" : "failed";
      return {
        ...state,
        tools: state.tools.map((t) => (t.callId === ev.data.call_id ? { ...t, status, summary: ev.data.summary } : t)),
      };
    }
    case "token": return { ...state, text: state.text + ev.data.text };
    case "job_cards": return { ...state, cards: ev.data.cards };
    case "tailoring_started": return { ...state, tailoring: { tailoringId: ev.data.tailoring_id, jobId: ev.data.job_id } };
    case "done":
      // The reply is complete; the caller turns the accumulated state into a ChatMessage.
      return { ...state, messageId: ev.data.message_id };
    case "error":
      // Terminal: the server gave up on this turn.
      return { ...state, status: "error", error: { message: ev.data.message, retryable: ev.data.retryable } };
  }
}

function reducer(state: StreamState, action: Action): StreamState {
  switch (action.type) {
    case "start": return { ...initialStreamState, status: "active", agentPhase: "thinking" };
    case "reset": return initialStreamState;
    case "fail": return { ...state, status: "error", error: { message: action.message, retryable: action.retryable } };
    case "event": return applyEvent(state, action.event);
  }
}

interface TurnRequest {
  conversationId: string;
  body: string;
  clientMessageId: string;
}

interface Options {
  /** Called once the reply is complete and persisted, with the finished message to append to the thread. */
  onComplete: (message: ChatMessage, clientMessageId: string) => void;
}

/**
 * Runs one chat turn: POST the message, open the SSE stream, fold events into
 * `state` for the live bubble, then hand the finished message to the caller.
 */
export function useChatStream({ onComplete }: Options) {
  const [state, dispatch] = useReducer(reducer, initialStreamState);
  const abortRef = useRef<AbortController | null>(null);
  const lastRequest = useRef<TurnRequest | null>(null);
  /** True when the last attempt ended with a server `error` event (as opposed to a dropped connection). */
  const failedTerminally = useRef(false);
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  // Leaving the page cancels the stream; the server still persists the reply.
  useEffect(() => () => abortRef.current?.abort(), []);

  const run = useCallback(async (req: TurnRequest) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    lastRequest.current = req;
    failedTerminally.current = false;
    dispatch({ type: "start" });

    // Local accumulator so we can build the final message without waiting for React state.
    let acc: StreamState = { ...initialStreamState, status: "active" };
    try {
      const ack = await api.sendMessage(req.conversationId, req.body, req.clientMessageId);
      for await (const ev of api.streamTurn(req.conversationId, ack.turn_id, controller.signal)) {
        acc = applyEvent(acc, ev);
        dispatch({ type: "event", event: ev });
        if (ev.event === "error") {
          failedTerminally.current = true;
          return;
        }
        if (ev.event === "done") {
          onCompleteRef.current(
            { id: ev.data.message_id, role: "assistant", body: acc.text, job_cards: acc.cards, tailoring_id: acc.tailoring?.tailoringId ?? null, created_at: new Date().toISOString() },
            req.clientMessageId,
          );
          dispatch({ type: "reset" });
          return;
        }
      }
      // Stream closed without done/error: treat as a dropped connection.
      dispatch({ type: "fail", message: "The connection dropped before the reply finished.", retryable: true });
    } catch (e) {
      if (controller.signal.aborted) return;
      dispatch({ type: "fail", message: describeError(e), retryable: !isApiError(e) || e.retryable });
    }
  }, []);

  /** Starts a new turn. Returns the client_message_id so the caller can tag its optimistic bubble. */
  const send = useCallback((conversationId: string, body: string, clientMessageId: string = uuid()) => {
    void run({ conversationId, body, clientMessageId });
    return clientMessageId;
  }, [run]);

  /**
   * Re-sends the last request. After a terminal `error` event the backend would hand back the
   * original failed turn for a reused client_message_id, so we send a fresh id to get a new attempt.
   * If the connection merely dropped (no terminal event), the SAME id is reused: the turn may still
   * be running or finished, and the server dedupes so no second turn is created.
   */
  const retry = useCallback(() => {
    const last = lastRequest.current;
    if (!last) return;
    void run(failedTerminally.current ? { ...last, clientMessageId: uuid() } : last);
  }, [run]);

  return { state, send, retry, busy: state.status === "active" };
}
