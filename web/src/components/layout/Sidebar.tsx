"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Bookmark, FileText, MessageSquarePlus, X } from "lucide-react";
import { useConversationList } from "@/hooks/useConversationList";
import { cn } from "@/lib/cn";
import { Logo } from "@/components/ui/Logo";
import { Skeleton } from "@/components/ui/Spinner";
import { buttonClasses } from "@/components/ui/Button";

const nav = [
  { href: "/app/resume", label: "Resume", icon: FileText },
  { href: "/app/saved", label: "Saved jobs", icon: Bookmark },
];

function NavLink({ href, label, icon: Icon }: (typeof nav)[number]) {
  const active = usePathname().startsWith(href);
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn("flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium", active ? "bg-brand/10 text-brand" : "text-muted hover:bg-sunken hover:text-ink")}
    >
      <Icon className="h-4 w-4" aria-hidden />
      {label}
    </Link>
  );
}

/** Conversation list + primary navigation. Rendered once; AppShell decides whether it is a column or a drawer. */
export function Sidebar({ onClose }: { onClose?: () => void }) {
  const { conversations, loading, error } = useConversationList();
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <Logo href="/app/chat" />
        {onClose ? (
          <button type="button" onClick={onClose} aria-label="Close menu" className="rounded-lg p-2 text-muted hover:bg-sunken lg:hidden">
            <X className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
      </div>

      <Link href="/app/chat" className={buttonClasses("primary", "md", "w-full")}>
        <MessageSquarePlus className="h-4 w-4" aria-hidden /> New chat
      </Link>

      <nav aria-label="Library" className="space-y-1">
        {nav.map((n) => <NavLink key={n.href} {...n} />)}
      </nav>

      <div className="min-h-0 flex-1">
        <h2 className="mb-2 px-3 text-xs font-semibold uppercase tracking-wider text-muted">Conversations</h2>
        <nav aria-label="Conversations" className="scroll-thin -mx-1 max-h-full space-y-0.5 overflow-y-auto px-1">
          {loading ? (
            <div className="space-y-2 px-2">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-9" />)}</div>
          ) : error ? (
            <p className="px-3 text-sm text-muted">Couldn&apos;t load conversations.</p>
          ) : conversations.length === 0 ? (
            <p className="px-3 text-sm text-muted">No conversations yet. Say hello!</p>
          ) : (
            conversations.map((c) => {
              const active = pathname === `/app/chat/${encodeURIComponent(c.id)}`;
              return (
                <Link
                  key={c.id}
                  href={`/app/chat/${encodeURIComponent(c.id)}`}
                  aria-current={active ? "page" : undefined}
                  title={c.title}
                  className={cn("block truncate rounded-lg px-3 py-2 text-sm", active ? "bg-sunken font-medium" : "text-ink/80 hover:bg-sunken")}
                >
                  {c.title}
                </Link>
              );
            })
          )}
        </nav>
      </div>
    </div>
  );
}
