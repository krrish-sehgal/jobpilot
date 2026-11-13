"use client";

import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import { Sidebar } from "./Sidebar";
import { ThemeToggle } from "./ThemeToggle";
import { UserMenu } from "./UserMenu";

/**
 * Desktop: fixed sidebar column + content. Mobile: the same Sidebar slides in
 * as a drawer over a backdrop, and closes on navigation or Escape.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const [drawer, setDrawer] = useState(false);
  const pathname = usePathname();

  useEffect(() => setDrawer(false), [pathname]);

  useEffect(() => {
    if (!drawer) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setDrawer(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [drawer]);

  return (
    <div className="flex h-dvh overflow-hidden">
      <aside className="hidden w-72 shrink-0 border-r border-line bg-surface lg:block" aria-label="Sidebar">
        <Sidebar />
      </aside>

      {drawer ? <div className="fixed inset-0 z-40 bg-ink/40 lg:hidden" onClick={() => setDrawer(false)} aria-hidden /> : null}
      <aside
        id="mobile-drawer"
        aria-label="Sidebar"
        className={`fixed inset-y-0 left-0 z-50 w-72 border-r border-line bg-surface transition-transform lg:hidden ${drawer ? "translate-x-0" : "-translate-x-full"}`}
        // Hidden drawers must not be tabbable.
        {...(drawer ? {} : ({ inert: "" } as object))}
      >
        <Sidebar onClose={() => setDrawer(false)} />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-paper px-4">
          <button type="button" onClick={() => setDrawer(true)} aria-label="Open menu" aria-expanded={drawer} aria-controls="mobile-drawer" className="rounded-lg p-2 text-muted hover:bg-sunken lg:hidden">
            <Menu className="h-5 w-5" aria-hidden />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <UserMenu />
          </div>
        </header>
        <main id="main" className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
