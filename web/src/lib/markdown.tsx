import Link from "next/link";
import type { ReactNode } from "react";

/*
  A deliberately tiny markdown renderer for assistant replies: paragraphs,
  "-" / "1." lists, "##" headings, **bold**, *italic*, `code` and [links](url).

  Safety: the model's output is untrusted text. We never build an HTML string.
  Parsing produces plain data, and rendering creates React elements, which
  escape text by construction. Links are allow-listed to http(s) and in-app
  paths, so `javascript:` URLs cannot be smuggled in.
*/

export type Inline =
  | { t: "text"; v: string }
  | { t: "bold" | "italic"; c: Inline[] }
  | { t: "code"; v: string }
  | { t: "link"; href: string; c: Inline[] };

export type Block =
  | { t: "p"; c: Inline[] }
  | { t: "h"; c: Inline[] }
  | { t: "ul" | "ol"; items: Inline[][] };

const TOKEN = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\)|\*[^*\s][^*]*\*)/;

export function isSafeHref(href: string): boolean {
  return /^https?:\/\//i.test(href) || (href.startsWith("/") && !href.startsWith("//"));
}

export function parseInline(src: string): Inline[] {
  const out: Inline[] = [];
  for (const part of src.split(TOKEN)) {
    if (!part) continue;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) out.push({ t: "bold", c: parseInline(part.slice(2, -2)) });
    else if (part.startsWith("`") && part.endsWith("`") && part.length > 2) out.push({ t: "code", v: part.slice(1, -1) });
    else if (part.startsWith("[")) {
      const m = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
      if (m && isSafeHref(m[2]!)) out.push({ t: "link", href: m[2]!, c: parseInline(m[1]!) });
      else out.push({ t: "text", v: m ? m[1]! : part }); // unsafe link: show the label only
    } else if (part.startsWith("*") && part.endsWith("*") && part.length > 2) out.push({ t: "italic", c: parseInline(part.slice(1, -1)) });
    else out.push({ t: "text", v: part });
  }
  return out;
}

export function parseMarkdown(src: string): Block[] {
  const blocks: Block[] = [];
  let para: string[] = [];
  const flush = () => {
    if (para.length) blocks.push({ t: "p", c: parseInline(para.join(" ")) });
    para = [];
  };

  for (const raw of src.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const numbered = /^\s*\d+[.)]\s+(.*)$/.exec(line);
    const heading = /^#{1,4}\s+(.*)$/.exec(line);
    const listMatch = bullet ?? numbered;
    const listType = bullet ? "ul" : "ol";

    if (!line.trim()) flush();
    else if (heading) { flush(); blocks.push({ t: "h", c: parseInline(heading[1]!) }); }
    else if (listMatch) {
      flush();
      const last = blocks[blocks.length - 1];
      if (last && last.t === listType) last.items.push(parseInline(listMatch[1]!));
      else blocks.push({ t: listType, items: [parseInline(listMatch[1]!)] });
    } else para.push(line.trim());
  }
  flush();
  return blocks;
}

function renderInline(nodes: Inline[]): ReactNode {
  return nodes.map((n, i) => {
    switch (n.t) {
      case "text": return n.v;
      case "bold": return <strong key={i} className="font-semibold">{renderInline(n.c)}</strong>;
      case "italic": return <em key={i}>{renderInline(n.c)}</em>;
      case "code": return <code key={i} className="rounded bg-sunken px-1 py-0.5 font-mono text-[0.85em]">{n.v}</code>;
      case "link": {
        const cls = "font-medium text-brand underline underline-offset-2";
        return n.href.startsWith("/") ? (
          <Link key={i} href={n.href} className={cls}>{renderInline(n.c)}</Link>
        ) : (
          <a key={i} href={n.href} target="_blank" rel="noopener noreferrer nofollow" className={cls}>{renderInline(n.c)}</a>
        );
      }
    }
  });
}

export function Markdown({ source }: { source: string }) {
  return (
    <div className="space-y-3 leading-relaxed">
      {parseMarkdown(source).map((b, i) => {
        switch (b.t) {
          case "p": return <p key={i}>{renderInline(b.c)}</p>;
          case "h": return <h3 key={i} className="font-display text-lg">{renderInline(b.c)}</h3>;
          case "ul": return <ul key={i} className="list-disc space-y-1 pl-5">{b.items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}</ul>;
          case "ol": return <ol key={i} className="list-decimal space-y-1 pl-5">{b.items.map((it, j) => <li key={j}>{renderInline(it)}</li>)}</ol>;
        }
      })}
    </div>
  );
}
