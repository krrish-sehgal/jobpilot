import { Suspense } from "react";
import type { Metadata } from "next";
import { LoginForm } from "@/components/layout/LoginForm";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="relative flex min-h-screen flex-col">
      <header className="flex items-center justify-between px-6 py-5">
        <Logo />
        <ThemeToggle />
      </header>
      <div className="flex flex-1 items-center justify-center px-4 pb-16">
        {/* useSearchParams needs a Suspense boundary during static rendering */}
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
      </div>
    </main>
  );
}
