/**
 * Server-Sent Events over `fetch`.
 *
 * Why not the browser's built-in `EventSource`? It cannot set request headers,
 * so there is no way to send `Authorization: Bearer ...`, and the contract
 * requires that header on the stream route. (Putting the token in the URL would
 * leak it into logs and history.) So we `fetch` the stream with our own
 * headers and parse the text/event-stream wire format ourselves. It is a small
 * format: blocks separated by a blank line, made of `field: value` lines.
 */

export interface SseMessage {
  event: string;
  data: string;
}

/**
 * Incremental parser. Network chunks can split anywhere (mid-line, mid-UTF-8
 * character is handled by the TextDecoder's stream mode), so `feed` buffers
 * partial lines and only emits a message once its terminating blank line has
 * arrived.
 */
export class SseParser {
  private buffer = "";
  private event = "";
  private data: string[] = [];

  feed(chunk: string): SseMessage[] {
    this.buffer += chunk;
    const out: SseMessage[] = [];
    // A chunk ending in "\r" may be the first half of "\r\n". Hold it back until the next chunk
    // says which it was, otherwise the "\n" would be read as a second, blank line and end the message early.
    let held = "";
    if (this.buffer.endsWith("\r")) {
      held = "\r";
      this.buffer = this.buffer.slice(0, -1);
    }
    // Lines may end in \n, \r\n or a lone \r.
    const lines = this.buffer.split(/\r\n|\n|\r/);
    // The last element is an incomplete line (possibly ""), keep it for the next chunk.
    this.buffer = (lines.pop() ?? "") + held;
    for (const line of lines) this.consumeLine(line, out);
    return out;
  }

  /** Call when the stream ends; emits a final message if the server omitted the trailing blank line. */
  flush(): SseMessage[] {
    const out: SseMessage[] = [];
    // A held-back trailing "\r" was a line terminator, not part of the text.
    const rest = this.buffer.replace(/\r$/, "");
    if (rest) {
      this.consumeLine(rest, out);
      this.buffer = "";
    }
    this.consumeLine("", out);
    return out;
  }

  private consumeLine(line: string, out: SseMessage[]) {
    if (line === "") {
      if (this.data.length > 0) out.push({ event: this.event || "message", data: this.data.join("\n") });
      this.event = "";
      this.data = [];
      return;
    }
    if (line.startsWith(":")) return; // comment / keep-alive heartbeat
    const idx = line.indexOf(":");
    const field = idx === -1 ? line : line.slice(0, idx);
    let value = idx === -1 ? "" : line.slice(idx + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    else if (field === "data") this.data.push(value);
    // `id` and `retry` are irrelevant here: we never auto-reconnect a turn.
  }
}

/** Reads a fetch response body and yields parsed SSE messages until the stream closes. */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseMessage> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  const parser = new SseParser();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      yield* parser.feed(decoder.decode(value, { stream: true }));
    }
    yield* parser.flush();
  } finally {
    // Releases the connection if the consumer stopped early (abort, unmount).
    reader.cancel().catch(() => undefined);
  }
}
