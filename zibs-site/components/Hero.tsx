export function Hero() {
  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-40 top-10 h-[420px] w-[420px] rounded-full bg-sky/15 blur-3xl" />
        <div className="absolute -right-32 bottom-0 h-[380px] w-[380px] rounded-full bg-sky/10 blur-3xl" />
      </div>
      <div className="relative mx-auto grid max-w-6xl gap-16 px-6 pb-24 pt-20 md:px-10 md:pt-28 lg:grid-cols-[1.1fr_0.9fr] lg:gap-12">
        <div className="flex flex-col justify-center">
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-sky/30 bg-sky/10 px-4 py-1.5 text-[0.65rem] uppercase tracking-ultra-wide text-sky">
            <span className="h-1.5 w-1.5 rounded-full bg-sky" />
            Patent Pending · USPTO · April 2026
          </span>
          <h1 className="mt-8 font-serif text-5xl leading-[1.05] text-ivory sm:text-6xl md:text-7xl">
            Keep the pouch.
            <br />
            <span className="italic text-sky">Lose the damage.</span>
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-relaxed text-ivory/75 md:text-xl">
            Zibs is a zero-nicotine buccal pouch that sits where Zyn sits — and
            sends collagen amino acids, CoQ10, and Vitamin C straight into your
            gum line for twenty minutes a day.
          </p>
          <div className="mt-10 flex flex-col items-start gap-4 sm:flex-row sm:items-center">
            <a
              href="#waitlist"
              className="inline-flex items-center justify-center rounded-full bg-sky px-7 py-3.5 text-sm font-semibold text-navy transition hover:bg-sky-soft"
            >
              Join the waitlist
            </a>
            <a
              href="#how-it-works"
              className="inline-flex items-center gap-2 text-sm font-medium uppercase tracking-ultra-wide text-ivory/70 transition hover:text-ivory"
            >
              How it works
              <span aria-hidden>→</span>
            </a>
          </div>
          <p className="mt-8 max-w-md text-sm text-ivory/50">
            Zero nicotine. Dietary supplement. Same tin. Same ritual. Different
            outcome.
          </p>
        </div>

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
  return (
    <svg
      viewBox="0 0 420 420"
      className="relative h-full w-full"
      role="img"
      aria-label="Zibs tin rendering"
    >
      <defs>
        <radialGradient id="tinFace" cx="50%" cy="42%" r="60%">
          <stop offset="0%" stopColor="#1c3360" />
          <stop offset="60%" stopColor="#0d1f3c" />
          <stop offset="100%" stopColor="#050d1f" />
        </radialGradient>
        <linearGradient id="tinRim" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#a8c4e0" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#3c5b8a" stopOpacity="0.6" />
        </linearGradient>
        <linearGradient id="tinShine" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stopColor="#a8c4e0" stopOpacity="0" />
          <stop offset="50%" stopColor="#a8c4e0" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#a8c4e0" stopOpacity="0" />
        </linearGradient>
      </defs>

      <ellipse
        cx="210"
        cy="340"
        rx="160"
        ry="22"
        fill="#000"
        opacity="0.55"
      />

      <ellipse
        cx="210"
        cy="245"
        rx="170"
        ry="50"
        fill="url(#tinRim)"
        opacity="0.85"
      />
      <ellipse cx="210" cy="232" rx="170" ry="50" fill="#0d1f3c" />
      <ellipse
        cx="210"
        cy="232"
        rx="170"
        ry="50"
        fill="url(#tinFace)"
      />
      <ellipse
        cx="210"
        cy="226"
        rx="170"
        ry="48"
        fill="none"
        stroke="#a8c4e0"
        strokeOpacity="0.55"
        strokeWidth="1.5"
      />
      <ellipse
        cx="210"
        cy="232"
        rx="156"
        ry="42"
        fill="none"
        stroke="#a8c4e0"
        strokeOpacity="0.18"
        strokeWidth="1"
      />
      <rect
        x="40"
        y="220"
        width="340"
        height="14"
        fill="url(#tinShine)"
        opacity="0.6"
      />

      <text
        x="210"
        y="226"
        textAnchor="middle"
        fontFamily="Cormorant Garamond, serif"
        fontSize="56"
        fill="#f5f1e8"
        letterSpacing="6"
      >
        ZIBS
      </text>
      <text
        x="210"
        y="252"
        textAnchor="middle"
        fontFamily="DM Sans, sans-serif"
        fontSize="9"
        fill="#a8c4e0"
        letterSpacing="6"
      >
        GUM HEALTH POUCH · 30 CT
      </text>
    </svg>
  );
}
