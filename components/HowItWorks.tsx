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

      <div className="relative mt-20">
        <div
          aria-hidden
          className="pointer-events-none absolute left-0 right-0 top-[2.3rem] hidden h-px bg-gradient-to-r from-transparent via-sky/40 to-transparent md:block"
        />
        <ol className="grid gap-12 md:grid-cols-3 md:gap-8">
          {STEPS.map((step) => (
            <li key={step.number} className="relative">
              <div className="flex items-center gap-4 md:flex-col md:items-start">
                <span className="relative inline-flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full border border-sky/40 bg-navy text-[0.7rem] uppercase tracking-ultra-wide text-sky md:h-[4.6rem] md:w-[4.6rem] md:text-base">
                  {step.number}
                </span>
                <h3 className="font-serif text-2xl text-ivory md:mt-7 md:text-3xl">
                  {step.title}
                </h3>
              </div>
              <p className="mt-4 max-w-md text-sm leading-relaxed text-ivory/70 md:mt-5 md:text-base">
                {step.body}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
