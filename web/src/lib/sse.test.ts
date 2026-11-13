import { describe, expect, it } from "vitest";
import { SseParser, readSse } from "./sse";

describe("SseParser", () => {
  it("parses event and data fields", () => {
    const p = new SseParser();
    expect(p.feed('event: token\ndata: {"text":"hi"}\n\n')).toEqual([{ event: "token", data: '{"text":"hi"}' }]);
  });

  it("buffers messages split across chunks", () => {
    const p = new SseParser();
    expect(p.feed("event: tok")).toEqual([]);
    expect(p.feed('en\ndata: {"a":')).toEqual([]);
    expect(p.feed("1}\n\nevent: done\ndata: {}\n\n")).toEqual([
      { event: "token", data: '{"a":1}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("handles CRLF, comments and multi-line data", () => {
    const p = new SseParser();
    const out = p.feed(": ping\r\nevent: x\r\ndata: a\r\ndata: b\r\n\r\n");
    expect(out).toEqual([{ event: "x", data: "a\nb" }]);
  });

  it("defaults the event name and flushes a trailing message", () => {
    const p = new SseParser();
    expect(p.feed("data: tail")).toEqual([]);
    expect(p.flush()).toEqual([{ event: "message", data: "tail" }]);
  });
});

describe("readSse", () => {
  it("reads a ReadableStream end to end", async () => {
    const enc = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(enc.encode("event: a\ndata: 1\n\nevent: b\nda"));
        c.enqueue(enc.encode("ta: 2\n\n"));
        c.close();
      },
    });
    const got = [];
    for await (const m of readSse(stream)) got.push(m);
    expect(got).toEqual([
      { event: "a", data: "1" },
      { event: "b", data: "2" },
    ]);
  });
});
