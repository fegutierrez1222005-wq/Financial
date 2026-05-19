"use client";

import { formatPrice, PRODUCT, useCart } from "./CartProvider";
import { Tin } from "./Tin";

export function Hero() {
  const { addToCart, openCart } = useCart();

  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-40 top-10 h-[420px] w-[420px] rounded-full bg-sky/15 blur-3xl" />
        <div className="absolute -right-32 bottom-0 h-[380px] w-[380px] rounded-full bg-sky/10 blur-3xl" />
      </div>
      <div className="relative mx-auto grid max-w-6xl gap-12 px-6 pb-28 pt-24 md:px-10 md:pt-32 lg:grid-cols-[1.15fr_1fr] lg:gap-16">
        <div className="flex flex-col justify-center">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-sky/30 bg-sky/10 px-4 py-1.5 text-[0.65rem] uppercase tracking-ultra-wide text-sky">
            <span className="h-1.5 w-1.5 rounded-full bg-sky" />
            Patent Pending · USPTO · April 2026
          </span>
          <h1 className="mt-8 font-serif text-[2.6rem] leading-[1.02] tracking-[-0.01em] text-ivory sm:text-[3.4rem] md:text-[4.25rem] md:leading-[0.98] md:tracking-[-0.015em] lg:text-[5rem]">
            <span className="block whitespace-nowrap">Keep the pouch.</span>
            <span className="block whitespace-nowrap italic text-sky">
              Lose the damage.
            </span>
          </h1>
          <p className="mt-8 max-w-xl text-lg leading-relaxed text-ivory/75 md:text-xl">
            Zibs is a zero-nicotine buccal pouch that sits where Zyn sits — and
            sends collagen amino acids, CoQ10, and Vitamin C straight into your
            gum line for twenty minutes a day.
          </p>

          <div className="mt-10 flex flex-col items-stretch gap-3 sm:flex-row sm:items-center">
            <button
              type="button"
              onClick={addToCart}
              className="inline-flex items-center justify-center gap-2 rounded-full bg-sky px-7 py-3.5 text-sm font-semibold text-navy transition hover:bg-sky-soft"
            >
              Add to cart
              <span className="text-navy/60">·</span>
              <span>{formatPrice(PRODUCT.priceCents)}</span>
            </button>
            <button
              type="button"
              onClick={openCart}
              className="inline-flex items-center justify-center gap-2 rounded-full border border-white/15 px-6 py-3.5 text-sm font-medium text-ivory transition hover:border-sky/40 hover:bg-white/5"
            >
              View cart
              <span aria-hidden>→</span>
            </button>
          </div>

          <p className="mt-8 max-w-md text-sm text-ivory/45">
            Pre-launch reservation. Zero nicotine · Dietary supplement · 30 ct
            tin.
          </p>
        </div>

        <a
          href="#how-it-works"
          aria-label="Scroll to how it works"
          className="absolute bottom-6 left-1/2 hidden -translate-x-1/2 items-center gap-2 text-[0.6rem] uppercase tracking-ultra-wide text-ivory/40 transition hover:text-ivory md:flex"
        >
          <span>Scroll</span>
          <span className="hero-scroll-line" aria-hidden />
        </a>

        <div className="relative flex items-center justify-center">
          <div className="relative h-[420px] w-[420px] max-w-full tin-float">
            <div className="absolute inset-0 rounded-full bg-sky/10 blur-3xl" />
            <Tin className="relative h-full w-full" />
          </div>
        </div>
      </div>
    </section>
  );
}

