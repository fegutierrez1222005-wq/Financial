"use client";

import { formatPrice, PRODUCT, useCart } from "./CartProvider";

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
          <div className="relative h-[420px] w-[420px] max-w-full">
            <div className="absolute inset-0 rounded-full bg-sky/10 blur-3xl" />
            <ZibsTin />
          </div>
        </div>
      </div>
    </section>
  );
}

function ZibsTin() {
  // Three-quarter view of a tin: thick chrome rim, recessed lid face, wall
  // depth visible at the bottom, soft top highlight + key light from upper-left.
  return (
    <svg
      viewBox="0 0 480 480"
      className="relative h-full w-full"
      role="img"
      aria-label="Zibs tin rendering"
    >
      <defs>
        {/* Lid face — recessed, lit from upper-left */}
        <radialGradient id="lidFace" cx="38%" cy="32%" r="78%">
          <stop offset="0%" stopColor="#243a66" />
          <stop offset="55%" stopColor="#0e2148" />
          <stop offset="100%" stopColor="#040c1d" />
        </radialGradient>

        {/* Outer chrome rim — top edge of the lid */}
        <linearGradient id="rimChrome" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#dfeaf6" />
          <stop offset="35%" stopColor="#a8c4e0" />
          <stop offset="65%" stopColor="#4d6c98" />
          <stop offset="100%" stopColor="#1d2c4f" />
        </linearGradient>

        {/* Side wall of the tin — body */}
        <linearGradient id="bodyWall" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#040c1d" />
          <stop offset="20%" stopColor="#0c1c3a" />
          <stop offset="50%" stopColor="#162a52" />
          <stop offset="80%" stopColor="#0c1c3a" />
          <stop offset="100%" stopColor="#040c1d" />
        </linearGradient>

        {/* Bottom rim — slightly warmer highlight */}
        <linearGradient id="bottomRim" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#2a4271" />
          <stop offset="100%" stopColor="#0a1530" />
        </linearGradient>

        {/* Lid specular highlight — broad and soft */}
        <radialGradient id="lidSpec" cx="38%" cy="20%" r="40%">
          <stop offset="0%" stopColor="#e9f1fb" stopOpacity="0.55" />
          <stop offset="60%" stopColor="#a8c4e0" stopOpacity="0.0" />
        </radialGradient>

        {/* Soft contact shadow */}
        <radialGradient id="ground" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#000" stopOpacity="0.65" />
          <stop offset="100%" stopColor="#000" stopOpacity="0" />
        </radialGradient>
      </defs>

      {/* Ground shadow */}
      <ellipse cx="240" cy="420" rx="170" ry="20" fill="url(#ground)" />

      {/* Tin body wall (the cylinder side) */}
      <path
        d="
          M 70 250
          a 170 50 0 0 0 340 0
          L 410 320
          a 170 50 0 0 1 -340 0
          Z
        "
        fill="url(#bodyWall)"
      />
      {/* Subtle hairline at bottom of side wall (catches light) */}
      <path
        d="M 70 320 a 170 50 0 0 0 340 0"
        fill="none"
        stroke="#a8c4e0"
        strokeOpacity="0.18"
        strokeWidth="1"
      />

      {/* Bottom rim ellipse (where tin meets the ground) */}
      <ellipse
        cx="240"
        cy="320"
        rx="170"
        ry="50"
        fill="url(#bottomRim)"
        opacity="0.95"
      />

      {/* Top chrome rim — outer ring */}
      <ellipse cx="240" cy="250" rx="178" ry="56" fill="url(#rimChrome)" />
      {/* Inner edge of the rim (creates lid recess) */}
      <ellipse cx="240" cy="250" rx="166" ry="48" fill="#08152e" />

      {/* Recessed lid face */}
      <ellipse cx="240" cy="248" rx="160" ry="44" fill="url(#lidFace)" />

      {/* Inner concentric debossed ring */}
      <ellipse
        cx="240"
        cy="248"
        rx="146"
        ry="40"
        fill="none"
        stroke="#a8c4e0"
        strokeOpacity="0.18"
        strokeWidth="1"
      />
      {/* Outer hairline circle catches highlight */}
      <ellipse
        cx="240"
        cy="244"
        rx="158"
        ry="42"
        fill="none"
        stroke="#dfeaf6"
        strokeOpacity="0.35"
        strokeWidth="1"
      />

      {/* Soft top-left specular on lid */}
      <ellipse
        cx="240"
        cy="248"
        rx="160"
        ry="44"
        fill="url(#lidSpec)"
      />

      {/* Brand mark */}
      <text
        x="240"
        y="246"
        textAnchor="middle"
        fontFamily="Cormorant Garamond, serif"
        fontSize="58"
        fill="#f5f1e8"
        letterSpacing="8"
      >
        ZIBS
      </text>
      <text
        x="240"
        y="272"
        textAnchor="middle"
        fontFamily="DM Sans, sans-serif"
        fontSize="9"
        fill="#a8c4e0"
        letterSpacing="6"
      >
        GUM HEALTH POUCH · 30 CT
      </text>

      {/* Subtle horizontal highlight band sweeping across the chrome rim */}
      <path
        d="M 80 246 Q 240 220 400 246"
        fill="none"
        stroke="#f5f1e8"
        strokeOpacity="0.25"
        strokeWidth="1.5"
      />
    </svg>
  );
}
