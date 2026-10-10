import Link from "next/link";
import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";
import { login } from "../actions";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <div>
      <h1 className="text-lg font-semibold tracking-tight text-ink-100">Sign in</h1>
      <p className="mt-1.5 text-sm text-ink-400">
        Continue to your research workspaces.
      </p>

      <AuthForm action={login} submitLabel="Sign in" className="mt-7">
        <div>
          <label className="field-label" htmlFor="email">
            Work email
          </label>
          <input
            id="email"
            name="email"
            type="email"
            required
            autoComplete="email"
            className="field-input"
            placeholder="analyst@fund.com"
          />
        </div>
        <div>
          <label className="field-label" htmlFor="password">
            Password
          </label>
          <input
            id="password"
            name="password"
            type="password"
            required
            autoComplete="current-password"
            className="field-input"
          />
        </div>
        <div>
          <label className="field-label" htmlFor="mfa_code">
            Authentication code (if enabled)
          </label>
          <input
            id="mfa_code"
            name="mfa_code"
            inputMode="numeric"
            autoComplete="one-time-code"
            className="field-input numeric"
            placeholder="000000"
          />
        </div>
      </AuthForm>

      <p className="mt-6 text-sm text-ink-400">
        No account?{" "}
        <Link href="/register" className="text-signal-info">
          Create one
        </Link>
      </p>
    </div>
  );
}
