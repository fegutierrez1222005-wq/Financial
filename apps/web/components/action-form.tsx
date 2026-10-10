"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";

import type { ActionState } from "@/app/(app)/actions";

export function SubmitButton({
  label,
  pendingLabel = "Working…",
  variant = "primary",
}: {
  label: string;
  pendingLabel?: string;
  variant?: "primary" | "secondary" | "danger";
}) {
  const { pending } = useFormStatus();
  const className = {
    primary: "button-primary",
    secondary: "button-secondary",
    danger: "button-danger",
  }[variant];
  return (
    <button type="submit" className={className} disabled={pending}>
      {pending ? pendingLabel : label}
    </button>
  );
}

/**
 * Wraps a server action with inline success and error reporting.
 * No button in this application is decorative: every one of them submits real work.
 */
export function ActionForm({
  action,
  submitLabel,
  pendingLabel,
  children,
  className = "",
}: {
  action: (state: ActionState, formData: FormData) => Promise<ActionState>;
  submitLabel: string;
  pendingLabel?: string;
  children: React.ReactNode;
  className?: string;
}) {
  const [state, formAction] = useActionState<ActionState, FormData>(action, {
    error: null,
    message: null,
  });

  return (
    <form action={formAction} className={className}>
      {children}
      {state.error ? (
        <p
          role="alert"
          className="mt-4 rounded border border-signal-negative/50 bg-signal-negative/10 px-3 py-2 text-sm text-ink-100"
        >
          {state.error}
        </p>
      ) : null}
      {state.message ? (
        <p
          role="status"
          className="mt-4 rounded border border-signal-positive/50 bg-signal-positive/10 px-3 py-2 text-sm text-ink-100"
        >
          {state.message}
        </p>
      ) : null}
      <div className="mt-5">
        <SubmitButton label={submitLabel} pendingLabel={pendingLabel} />
      </div>
    </form>
  );
}
