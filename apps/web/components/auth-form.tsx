"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import type { FormState } from "@/app/(auth)/actions";

function SubmitButton({ label }: { label: string }) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" className="button-primary w-full" disabled={pending}>
      {pending ? "Working…" : label}
    </button>
  );
}

export function AuthForm({
  action,
  submitLabel,
  children,
  className = "",
}: {
  action: (state: FormState, formData: FormData) => Promise<FormState>;
  submitLabel: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [state, formAction] = useActionState<FormState, FormData>(action, { error: null });

  return (
    <form action={formAction} className={`space-y-4 ${className}`} noValidate>
      {children}
      {state.error ? (
        <p
          role="alert"
          className="rounded border border-signal-negative/50 bg-signal-negative/10 px-3 py-2 text-sm text-ink-100"
        >
          {state.error}
        </p>
      ) : null}
      <SubmitButton label={submitLabel} />
    </form>
  );
}
