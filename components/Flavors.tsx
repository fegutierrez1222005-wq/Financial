import { Reveal } from "./Reveal";

const FLAVORS = [
  {
    id: "wintergreen",
    name: "Wintergreen",
    note: "Cool, classic, gum-friendly",
    palette: {
      face: ["#0e2148", "#0a1530", "#04091a"] as [string, string, string],
      rim: ["#a8c4e0", "#3c5b8a"] as [string, string],
      label: "#a8c4e0",
      glow: "from-sky/30 via-sky/5 to-transparent",
      tag: "WINTERGREEN",
    },
  },
  {
    id: "cool-mint",
    name: "Cool Mint",
    note: "Crisp peppermint, low sweetness",
    palette: {
      face: ["#0c3030", "#072020", "#021212"] as [string, string, string],
      rim: ["#c7eee0", "#3a7e74"] as [string, string],
      label: "#bce6d4",
      glow: "from-emerald-300/25 via-teal-300/10 to-transparent",
      tag: "COOL MINT",
    },
  },
  {
    id: "citrus",
    name: "Citrus",
    note: "Bright, Vitamin-C forward",
    palette: {
      face: ["#3a2410", "#241608", "#120a04"] as [string, string, string],
      rim: ["#f6d8a4", "#a06d2c"] as [string, string],
      label: "#f0c98a",
      glow: "from-amber-300/30 via-orange-300/10 to-transparent",
      tag: "CITRUS",
    },
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
          {FLAVORS.map((flavor, index) => (
            <Reveal
              as="li"
              delay={index * 100}
              key={flavor.id}
              className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-7 transition-all duration-500 hover:-translate-y-1 hover:border-sky/30 hover:shadow-[0_30px_60px_-30px_rgba(168,196,224,0.25)]"
            >
              <div
                className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${flavor.palette.glow} opacity-70 transition group-hover:opacity-100`}
              />
              <div className="relative flex h-56 items-center justify-center transition-transform duration-500 group-hover:-translate-y-1">
                <FlavorTin
                  id={flavor.id}
                  tag={flavor.palette.tag}
                  face={flavor.palette.face}
                  rim={flavor.palette.rim}
                  label={flavor.palette.label}
                />
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
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

function FlavorTin({
  id,
  tag,
  face,
  rim,
  label,
}: {
  id: string;
  tag: string;
  face: [string, string, string];
  rim: [string, string];
  label: string;
}) {
  const faceId = `face-${id}`;
  const rimId = `rim-${id}`;
  return (
    <svg viewBox="0 0 320 220" className="h-full w-full" aria-hidden>
      <defs>
        <radialGradient id={faceId} cx="38%" cy="32%" r="78%">
          <stop offset="0%" stopColor={face[0]} />
          <stop offset="60%" stopColor={face[1]} />
          <stop offset="100%" stopColor={face[2]} />
        </radialGradient>
        <linearGradient id={rimId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor={rim[0]} />
          <stop offset="100%" stopColor={rim[1]} />
        </linearGradient>
      </defs>
      <ellipse cx="160" cy="190" rx="120" ry="12" fill="#000" opacity="0.45" />
      <ellipse cx="160" cy="120" rx="130" ry="38" fill={`url(#${rimId})`} opacity="0.85" />
      <ellipse cx="160" cy="112" rx="130" ry="38" fill={face[1]} />
      <ellipse cx="160" cy="112" rx="130" ry="38" fill={`url(#${faceId})`} />
      <ellipse
        cx="160"
        cy="106"
        rx="130"
        ry="36"
        fill="none"
        stroke={rim[0]}
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
        fill={label}
        letterSpacing="4"
      >
        {tag} · 30 CT
      </text>
    </svg>
  );
}
