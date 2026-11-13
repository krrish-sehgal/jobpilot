"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { isMockMode } from "@/lib/api";
import { describeError } from "@/lib/api/errors";
import { useAuth } from "@/lib/auth/AuthProvider";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { ErrorNotice } from "@/components/ui/ErrorNotice";

type Step = "email" | "code";

const inputClass =
  "h-11 w-full rounded-lg border border-line bg-paper px-3 text-base placeholder:text-muted/70 focus-visible:border-brand";

/** Two-step passwordless sign-in: email -> 6-digit code (contract: /auth/request-code, /auth/verify-code). */
export function LoginForm() {
  const { status, requestCode, verifyCode } = useAuth();
  const router = useRouter();
  const params = useSearchParams();
  // Only allow same-site return paths, so ?next= can't be used as an open redirect.
  const rawNext = params.get("next") ?? "";
  const next = rawNext.startsWith("/app") ? rawNext : "/app/chat";

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, router, next]);

  async function submitEmail(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await requestCode(email.trim());
      setStep("code");
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await verifyCode(email.trim(), code);
      router.replace(next);
    } catch (err) {
      setError(describeError(err));
      setBusy(false);
    }
  }

  return (
    <Card className="w-full max-w-md p-8">
      <h1 className="font-display text-3xl">{step === "email" ? "Welcome aboard" : "Check your inbox"}</h1>
      <p className="mt-2 text-sm text-muted">
        {step === "email"
          ? "Enter your email and we'll send a 6-digit code. No password to remember."
          : `We sent a 6-digit code to ${email}. It expires in 10 minutes.`}
      </p>

      {step === "email" ? (
        <form onSubmit={submitEmail} className="mt-6 space-y-4">
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium">Email address</label>
            <input id="email" type="email" required autoComplete="email" autoFocus value={email} onChange={(e) => setEmail(e.target.value)} className={inputClass} placeholder="you@example.com" />
          </div>
          {error ? <ErrorNotice message={error} /> : null}
          <Button type="submit" size="lg" className="w-full" loading={busy}>Send code</Button>
        </form>
      ) : (
        <form onSubmit={submitCode} className="mt-6 space-y-4">
          <div>
            <label htmlFor="code" className="mb-1.5 block text-sm font-medium">6-digit code</label>
            <input
              id="code" inputMode="numeric" pattern="\d{6}" maxLength={6} required autoComplete="one-time-code" autoFocus
              value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              className={`${inputClass} text-center font-mono text-2xl tracking-[0.5em]`} placeholder="000000"
            />
          </div>
          {error ? <ErrorNotice message={error} /> : null}
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={code.length !== 6}>Verify and continue</Button>
          <button type="button" className="w-full text-sm text-muted underline-offset-4 hover:underline" onClick={() => { setStep("email"); setCode(""); setError(null); }}>
            Use a different email
          </button>
        </form>
      )}

      {isMockMode ? (
        <p className="mt-6 rounded-lg bg-signal/10 p-3 text-xs text-ink">
          <strong>Demo mode.</strong> No email is sent. Enter any address, then any 6-digit code (except 000000).
        </p>
      ) : null}
    </Card>
  );
}
