const FLAVORS = [
  {
    name: "Wintergreen",
    note: "Cool, classic, gum-friendly",
    accent: "from-sky/40 via-sky/10 to-transparent",
  },
  {
    name: "Cool Mint",
    note: "Crisp peppermint, low sweetness",
    accent: "from-emerald-200/30 via-sky/10 to-transparent",
  },
  {
    name: "Citrus",
    note: "Bright, Vitamin-C forward",
    accent: "from-amber-200/30 via-sky/10 to-transparent",
  },
];

export function Flavors() {
  return (
    <section className="relative overflow-hidden bg-navy py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-10">
        <div className="mb-12 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="eyebrow">Flavors</span>
            <h2 className="mt-4 max-w-xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
              Three at launch.
              <br />
              <span className="italic text-sky">More on the way.</span>
            </h2>
          </div>
          <p className="max-w-md text-base leading-relaxed text-ivory/65">
            Same formula in every tin. Flavor systems chosen for low acidity,
            no added sugar, and no irritants — the whole point is being kind to
            your gums.
          </p>
        </div>

        <ul className="grid gap-6 md:grid-cols-3">
          {FLAVORS.map((flavor) => (
            <li
              key={flavor.name}
              className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-7 transition hover:border-sky/30"
            >
              <div
                className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${flavor.accent} opacity-70 transition group-hover:opacity-100`}
              />
              <div className="relative flex h-56 items-center justify-center">
                <FlavorTin label={flavor.name} />
              </div>
              <div className="relative mt-6 flex items-end justify-between">
                <div>
                  <h3 className="font-serif text-2xl text-ivory">
                    {flavor.name}
                  </h3>
                  <p className="mt-1 text-sm text-ivory/60">{flavor.note}</p>
                </div>
                <span className="rounded-full border border-white/15 px-3 py-1 text-[0.6rem] uppercase tracking-ultra-wide text-ivory/55">
                  Coming soon
                </span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

function FlavorTin({ label }: { label: string }) {
  return (
    <svg viewBox="0 0 320 220" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id={`face-${label}`} cx="50%" cy="42%" r="60%">
          <stop offset="0%" stopColor="#1c3360" />
          <stop offset="60%" stopColor="#0d1f3c" />
          <stop offset="100%" stopColor="#050d1f" />
        </radialGradient>
      </defs>
      <ellipse cx="160" cy="190" rx="120" ry="12" fill="#000" opacity="0.45" />
      <ellipse cx="160" cy="120" rx="130" ry="38" fill="#a8c4e0" opacity="0.7" />
      <ellipse cx="160" cy="112" rx="130" ry="38" fill="#0d1f3c" />
      <ellipse cx="160" cy="112" rx="130" ry="38" fill={`url(#face-${label})`} />
      <ellipse
        cx="160"
        cy="106"
        rx="130"
        ry="36"
        fill="none"
        stroke="#a8c4e0"
        strokeOpacity="0.5"
        strokeWidth="1.2"
      />
      <text
        x="160"
        y="108"
        textAnchor="middle"
        fontFamily="Cormorant Garamond, serif"
        fontSize="36"
        fill="#f5f1e8"
        letterSpacing="4"
      >
        ZIBS
      </text>
      <text
        x="160"
        y="128"
        textAnchor="middle"
        fontFamily="DM Sans, sans-serif"
        fontSize="7"
        fill="#a8c4e0"
        letterSpacing="4"
      >
        {label.toUpperCase()} · 30 CT
      </text>
    </svg>
  );
}
