import { Reveal } from "./Reveal";

const PHASES = [
  {
    label: "20 minutes",
    title: "Buffered absorption",
    body: "Pouch sits flush against gum tissue. HPMC mesh holds steady release as collagen amino acids, CoQ10, and Vitamin C diffuse straight through the buccal membrane.",
  },
  {
    label: "Day 1",
    title: "Cofactors restocked",
    body: "Vitamin C and L-Hydroxyproline — the rate-limiting cofactors for gum collagen synthesis — reach saturating local concentrations within a single sitting.",
  },
  {
    label: "Week 4",
    title: "Tissue rebuilds",
    body: "With daily cofactor delivery, gingival fibroblasts have the substrate they need. Studies on local CoQ10 and amino acid delivery show measurable pocket-depth and inflammation drops by week four.",
  },
  {
    label: "Long term",
    title: "Net-zero ritual",
    body: "The same twenty minutes a day that used to cost you collagen now restocks it. Same tin. Same hand motion. Different outcome.",
  },
];

export function Timeline() {
  return (
    <section className="relative overflow-hidden border-y border-white/5 bg-navy-deep py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-10">
        <div className="mb-16 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="eyebrow">The arc</span>
            <h2 className="mt-4 max-w-2xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
              From the first pouch to
              <br />
              <span className="italic text-sky">the long arc.</span>
            </h2>
          </div>
          <div className="flex flex-wrap gap-2 text-[0.65rem] uppercase tracking-ultra-wide text-ivory/45">
            {PHASES.map((phase) => (
              <span
                key={phase.label}
                className="rounded-full border border-white/10 px-3 py-1.5"
              >
                {phase.label}
              </span>
            ))}
          </div>
        </div>

        <ol className="relative grid gap-px overflow-hidden rounded-3xl border border-white/10 bg-white/5 md:grid-cols-4">
          {PHASES.map((phase, index) => (
            <Reveal
              as="li"
              key={phase.label}
              delay={index * 90}
              className="relative flex flex-col bg-navy-deep p-7 md:p-8"
            >
              <div className="font-serif text-5xl leading-none text-sky/70">
                {String(index + 1).padStart(2, "0")}
              </div>
              <div className="mt-5 text-[0.65rem] uppercase tracking-ultra-wide text-sky">
                {phase.label}
              </div>
              <h3 className="mt-2 font-serif text-2xl text-ivory">
                {phase.title}
              </h3>
              <p className="mt-3 text-sm leading-relaxed text-ivory/65">
                {phase.body}
              </p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
