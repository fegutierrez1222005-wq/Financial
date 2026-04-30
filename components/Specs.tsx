import { Reveal } from "./Reveal";

const SPECS = [
  { key: "Format", value: "Mucoadhesive buccal pouch · non-dissolving mesh" },
  { key: "Fill weight", value: "400–500 mg per pouch" },
  { key: "Contact time", value: "20–30 min sustained release" },
  { key: "Target pH", value: "6.2–6.8 (buffered)" },
  { key: "Active release window", value: "60–80% within first 30 min" },
  { key: "Regulatory", value: "Dietary supplement · No FDA drug approval" },
];

export function Specs() {
  return (
    <section id="specs" className="relative bg-navy py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-10">
        <Reveal className="mb-12 max-w-3xl">
          <span className="eyebrow">Spec sheet</span>
          <h2 className="mt-4 font-serif text-4xl leading-tight text-ivory md:text-5xl">
            Built like a clinical
            <br />
            <span className="italic text-sky">delivery system.</span>
          </h2>
        </Reveal>

        <Reveal delay={120}>
          <dl className="divide-y divide-white/10 border-y border-white/10">
            {SPECS.map((spec) => (
              <div
                key={spec.key}
                className="grid grid-cols-1 items-baseline gap-2 py-5 md:grid-cols-[12rem_1fr] md:gap-10"
              >
                <dt className="text-[0.65rem] uppercase tracking-ultra-wide text-sky">
                  {spec.key}
                </dt>
                <dd className="font-serif text-xl text-ivory md:text-2xl">
                  {spec.value}
                </dd>
              </div>
            ))}
          </dl>
        </Reveal>
      </div>
    </section>
  );
}
