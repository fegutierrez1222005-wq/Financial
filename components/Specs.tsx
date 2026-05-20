import { Reveal } from "./Reveal";

type Spec = {
  key: string;
  value: string;
  detail: string;
  icon: "pouch" | "scale" | "clock" | "ph" | "wave" | "shield";
};

const SPECS: Spec[] = [
  {
    key: "Format",
    value: "Buccal pouch",
    detail: "Non-dissolving mucoadhesive mesh",
    icon: "pouch",
  },
  {
    key: "Fill weight",
    value: "400–500 mg",
    detail: "Per pouch",
    icon: "scale",
  },
  {
    key: "Contact time",
    value: "20–30 min",
    detail: "Sustained release",
    icon: "clock",
  },
  {
    key: "Target pH",
    value: "6.2–6.8",
    detail: "Buffered, gum-friendly",
    icon: "ph",
  },
  {
    key: "Release window",
    value: "60–80%",
    detail: "Of actives within first 30 min",
    icon: "wave",
  },
  {
    key: "Regulatory",
    value: "Dietary supplement",
    detail: "No FDA drug approval required",
    icon: "shield",
  },
];

export function Specs() {
  return (
    <section id="specs" className="relative bg-navy py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-10">
        <Reveal className="mb-14 max-w-3xl">
          <span className="eyebrow">Spec sheet</span>
          <h2 className="mt-4 font-serif text-4xl leading-tight text-ivory md:text-5xl">
            Built like a clinical
            <br />
            <span className="italic text-sky">delivery system.</span>
          </h2>
        </Reveal>

        <ul className="grid gap-px overflow-hidden rounded-3xl border border-white/10 bg-white/5 md:grid-cols-3">
          {SPECS.map((spec, i) => (
            <Reveal
              as="li"
              key={spec.key}
              delay={i * 60}
              className="group relative bg-navy-deep p-7 transition-colors duration-300 hover:bg-[#0b1937] md:p-8"
            >
              <div className="flex items-start justify-between">
                <div className="text-[0.65rem] uppercase tracking-ultra-wide text-sky">
                  {spec.key}
                </div>
                <SpecIcon name={spec.icon} />
              </div>
              <div className="mt-7 font-serif text-3xl leading-[1.05] text-ivory md:text-[2rem]">
                {spec.value}
              </div>
              <div className="mt-2 text-sm text-ivory/55">{spec.detail}</div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}

function SpecIcon({ name }: { name: Spec["icon"] }) {
  const common = {
    width: 22,
    height: 22,
    viewBox: "0 0 24 24",
    fill: "none" as const,
    stroke: "currentColor" as const,
    strokeWidth: 1.4,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "text-sky/70 transition group-hover:text-sky",
    "aria-hidden": true,
  };
  switch (name) {
    case "pouch":
      return (
        <svg {...common}>
          <ellipse cx="12" cy="12" rx="8" ry="5" />
          <path d="M4 12c2 1.5 5 2.5 8 2.5s6-1 8-2.5" />
        </svg>
      );
    case "scale":
      return (
        <svg {...common}>
          <path d="M12 4v16" />
          <path d="M5 8l3 7-3 .5L5 8z" />
          <path d="M19 8l-3 7 3 .5-0-7.5z" transform="translate(0)" />
          <path d="M5 8h14" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v4l3 2" />
        </svg>
      );
    case "ph":
      return (
        <svg {...common}>
          <path d="M5 19c3-3 5-3 7-1s4 2 7-1" />
          <path d="M7 13a3 3 0 1 1 6 0v6" />
          <path d="M17 19v-6" />
          <path d="M14 16h6" />
        </svg>
      );
    case "wave":
      return (
        <svg {...common}>
          <path d="M3 12c2-3 4-3 6 0s4 3 6 0 4-3 6 0" />
          <path d="M3 17c2-3 4-3 6 0s4 3 6 0 4-3 6 0" opacity="0.55" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6l8-3z" />
          <path d="M9.5 12l2 2 3.5-4" />
        </svg>
      );
  }
}
