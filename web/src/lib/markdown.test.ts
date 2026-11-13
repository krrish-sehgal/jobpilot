import { describe, expect, it } from "vitest";
import { isSafeHref, parseInline, parseMarkdown } from "./markdown";

describe("parseInline", () => {
  it("parses bold, code and links", () => {
    expect(parseInline("a **b** `c` [d](/x)")).toEqual([
      { t: "text", v: "a " },
      { t: "bold", c: [{ t: "text", v: "b" }] },
      { t: "text", v: " " },
      { t: "code", v: "c" },
      { t: "text", v: " " },
      { t: "link", href: "/x", c: [{ t: "text", v: "d" }] },
    ]);
  });

  it("drops javascript: links but keeps the label", () => {
    const nodes = parseInline("[click](javascript:alert(1))");
    expect(nodes.some((n) => n.t === "link")).toBe(false);
    expect(nodes[0]).toEqual({ t: "text", v: "click" });
    expect(isSafeHref("//evil.example")).toBe(false);
    expect(isSafeHref("https://ok.example")).toBe(true);
  });

  it("rejects protocol-relative and backslash paths, accepts in-app paths", () => {
    expect(isSafeHref("//evil.com")).toBe(false);
    expect(isSafeHref("/\\evil.com")).toBe(false);
    expect(isSafeHref("/\\/evil.com")).toBe(false);
    expect(isSafeHref("/app/jobs/123")).toBe(true);
    expect(isSafeHref("javascript:alert(1)")).toBe(false);
    expect(isSafeHref("data:text/html,x")).toBe(false);
  });

  it("leaves an unclosed bold marker as plain text while streaming", () => {
    expect(parseInline("hello **wor")).toEqual([{ t: "text", v: "hello **wor" }]);
  });
});

describe("parseMarkdown", () => {
  it("groups list items and separates paragraphs", () => {
    const blocks = parseMarkdown("Intro line\ncontinued\n\n- one\n- two\n\n1. first\n2. second");
    expect(blocks.map((b) => b.t)).toEqual(["p", "ul", "ol"]);
    expect(blocks[1]).toMatchObject({ items: [[{ t: "text", v: "one" }], [{ t: "text", v: "two" }]] });
  });

  it("treats raw HTML as text, never markup", () => {
    expect(parseMarkdown("<script>alert(1)</script>")).toEqual([{ t: "p", c: [{ t: "text", v: "<script>alert(1)</script>" }] }]);
  });
});
