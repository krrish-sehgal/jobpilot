"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";
import { useAuth } from "@/lib/auth/AuthProvider";

/** Avatar button + popover. Closes on outside click and Escape; focus returns to the button. */
export function UserMenu() {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!root.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        button.current?.focus();
      }
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const initials = (user?.full_name ?? user?.email ?? "?").split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((p) => p[0]!.toUpperCase()).join("");

  return (
    <div ref={root} className="relative">
      <button
        ref={button}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        onClick={() => setOpen((o) => !o)}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-brand text-sm font-semibold text-brand-ink"
      >
        {initials}
      </button>
      {open ? (
        <div role="menu" className="absolute right-0 top-11 z-30 w-60 rounded-xl border border-line bg-surface p-2 shadow-card">
          <div className="px-3 py-2">
            <p className="truncate text-sm font-medium">{user?.full_name ?? "Signed in"}</p>
            <p className="truncate text-xs text-muted">{user?.email}</p>
          </div>
          <button
            role="menuitem"
            type="button"
            onClick={() => { logout(); router.replace("/login"); }}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-sunken"
          >
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}
