const STEPS = [
  {
    number: "01",
    title: "Place it",
    body: "Tuck a single Zibs pouch between cheek and gum, just like the pouch you already use. Same tin format, same muscle memory.",
  },
  {
    number: "02",
    title: "Let it work",
    body: "Mucoadhesive HPMC mesh holds the pouch flush against gum tissue for twenty to thirty minutes of buffered, sustained release.",
  },
  {
    number: "03",
    title: "Protect your gums",
    body: "Collagen amino acids, CoQ10, and Vitamin C absorb directly through the buccal membrane — the rate-limiting building blocks of gum tissue, restocked daily.",
  },
];

export function HowItWorks() {
  return (
    <section
      id="how-it-works"
      className="relative mx-auto max-w-6xl px-6 py-24 md:px-10 md:py-32"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <span className="eyebrow">How it works</span>
          <h2 className="mt-4 max-w-2xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
            One pouch. Twenty minutes.
            <br />
            <span className="italic text-sky">Net zero damage.</span>
          </h2>
        </div>
        <p className="max-w-md text-base leading-relaxed text-ivory/70">
          Designed for the generation that won&apos;t quit Zyn but won&apos;t
          let it destroy their smile either. The ritual stays. The damage
          doesn&apos;t.
        </p>
      </div>

      <div className="mt-16 grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/5 md:grid-cols-3">
        {STEPS.map((step) => (
          <div
            key={step.number}
            className="relative bg-navy p-8 md:p-10"
          >
            <div className="font-serif text-7xl text-sky/70">
              {step.number}
            </div>
            <h3 className="mt-5 font-serif text-2xl text-ivory md:text-3xl">
              {step.title}
            </h3>
            <p className="mt-4 text-sm leading-relaxed text-ivory/70 md:text-base">
              {step.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
