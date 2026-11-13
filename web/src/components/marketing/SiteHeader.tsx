import Link from "next/link";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { LinkButton } from "@/components/ui/Button";

export function SiteHeader() {
  return (
    <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
      <Logo />
      <nav aria-label="Main" className="flex items-center gap-2">
        <Link href="#how" className="hidden rounded-lg px-3 py-2 text-sm text-muted hover:text-ink sm:block">How it works</Link>
        <ThemeToggle />
        <LinkButton href="/login" size="sm" variant="secondary">Sign in</LinkButton>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-line px-6 py-8 text-center text-sm text-muted">
      JobPilot is a demo project. All companies and postings shown in demo mode are fictional.
    </footer>
  );
}
