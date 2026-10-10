import Link from "next/link";
import type { Metadata } from "next";

import { AuthForm } from "@/components/auth-form";
import { register } from "../actions";

export const metadata: Metadata = { title: "Create an account" };

export default function RegisterPage() {
  return (
    <div>
      <h1 className="text-lg font-semibold tracking-tight text-ink-100">Create an account</h1>
      <p className="mt-1.5 text-sm text-ink-400">
        You will get an empty workspace and, optionally, a seeded demo workspace.
      </p>

      <AuthForm action={register} submitLabel="Create account" className="mt-7">
        <div>
          <label className="field-label" htmlFor="full_name">
            Full name
          </label>
          <input id="full_name" name="full_name" autoComplete="name" className="field-input" />
        </div>
        <div>
          <label className="field-label" htmlFor="organization_name">
            Organization
          </label>
          <input
            id="organization_name"
            name="organization_name"
            autoComplete="organization"
            className="field-input"
            placeholder="Fund or research group"
          />
        </div>
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
            minLength={12}
            autoComplete="new-password"
            className="field-input"
          />
          <p className="field-hint">
            At least 12 characters, including an uppercase letter and a digit.
          </p>
        </div>
        <label className="flex items-start gap-2.5 text-sm text-ink-300">
          <input
            type="checkbox"
            name="seed_demo"
            defaultChecked
            className="mt-0.5 h-4 w-4 rounded-sm border-ink-600 bg-ink-850"
          />
          <span>
            Seed the demo workspace
            <span className="mt-1 block text-2xs leading-relaxed text-ink-500">
              ACME Technologies is a fictional issuer with synthetic filings and prices, labelled
              as demo data wherever it appears. It gives you a working corpus, two agents and a
              golden dataset to try the pipeline against.
            </span>
          </span>
        </label>
      </AuthForm>

      <p className="mt-6 text-sm text-ink-400">
        Already have an account?{" "}
        <Link href="/login" className="text-signal-info">
          Sign in
        </Link>
      </p>
    </div>
  );
}
