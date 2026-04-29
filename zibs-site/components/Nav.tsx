"use client";

import Link from "next/link";

export function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-navy/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5 md:px-10">
        <Link href="/" className="flex items-center gap-3">
          <span className="font-serif text-2xl tracking-tight text-ivory">
            Zibs
          </span>
          <span className="hidden text-[0.6rem] uppercase tracking-ultra-wide text-sky sm:inline">
            Patent Pending
          </span>
        </Link>
        <nav className="hidden items-center gap-8 text-sm text-ivory/70 md:flex">
          <a href="#how-it-works" className="hover:text-ivory">
            How it works
          </a>
          <a href="#ingredients" className="hover:text-ivory">
            Ingredients
          </a>
          <a href="#waitlist" className="hover:text-ivory">
            Waitlist
          </a>
        </nav>
        <a
          href="#waitlist"
          className="rounded-full border border-sky/40 bg-sky px-4 py-2 text-sm font-medium text-navy transition hover:bg-sky-soft md:px-5"
        >
          Join Waitlist
        </a>
      </div>
    </header>
  );
}
