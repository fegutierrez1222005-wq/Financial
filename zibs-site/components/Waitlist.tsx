"use client";

import { useState } from "react";

type Status = "idle" | "loading" | "success" | "error";

export function Waitlist() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [message, setMessage] = useState<string>("");

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "loading") return;

    setStatus("loading");
    setMessage("");

    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      const data = (await response
        .json()
        .catch(() => ({}))) as { error?: string };

      if (!response.ok) {
        throw new Error(data.error ?? "Something went wrong. Try again.");
      }

      setStatus("success");
      setEmail("");
    } catch (error) {
      setStatus("error");
      setMessage(
        error instanceof Error
          ? error.message
          : "Something went wrong. Try again."
      );
    }
  }

  return (
    <section
      id="waitlist"
      className="relative overflow-hidden bg-navy py-24 md:py-32"
    >
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-3xl px-6 text-center md:px-10">
        <span className="eyebrow">Waitlist now open</span>
        <h2 className="mt-5 font-serif text-4xl leading-tight text-ivory md:text-6xl">
          Be first in line when
          <br />
          <span className="italic text-sky">Zibs ships.</span>
        </h2>
        <p className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-ivory/70 md:text-lg">
          Drop your email. You&apos;ll get the first 30-count tin, founder
          pricing for life, and a heads-up the moment we open the door.
        </p>

        {status === "success" ? (
          <SuccessState />
        ) : (
          <form
            onSubmit={handleSubmit}
            className="mx-auto mt-10 flex w-full max-w-xl flex-col gap-3 sm:flex-row"
          >
            <label htmlFor="waitlist-email" className="sr-only">
              Email address
            </label>
            <input
              id="waitlist-email"
              type="email"
              required
              autoComplete="email"
              inputMode="email"
              placeholder="you@school.edu"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="flex-1 rounded-full border border-white/15 bg-white/5 px-6 py-4 text-base text-ivory placeholder-ivory/40 outline-none transition focus:border-sky focus:bg-white/10"
            />
            <button
              type="submit"
              disabled={status === "loading"}
              className="rounded-full bg-sky px-7 py-4 text-sm font-semibold uppercase tracking-ultra-wide text-navy transition hover:bg-sky-soft disabled:cursor-not-allowed disabled:opacity-60"
            >
              {status === "loading" ? "Adding…" : "Join the list"}
            </button>
          </form>
        )}

        {status === "error" && (
          <p className="mt-4 text-sm text-red-300">{message}</p>
        )}

        <p className="mt-6 text-xs uppercase tracking-ultra-wide text-ivory/40">
          No spam. One launch email. Unsubscribe anytime.
        </p>
      </div>
    </section>
  );
}

function SuccessState() {
  return (
    <div className="mx-auto mt-12 max-w-xl rounded-2xl border border-sky/30 bg-sky/10 p-8 text-left">
      <div className="font-serif text-3xl text-ivory">You&apos;re on the list.</div>
      <p className="mt-3 text-sm leading-relaxed text-ivory/75">
        We&apos;ll send one email when Zibs ships — with founder pricing locked
        in for the first tins out the door. Until then, keep your eyes on your
        gum line.
      </p>
    </div>
  );
}
