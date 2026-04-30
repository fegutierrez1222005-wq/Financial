import { Reveal } from "./Reveal";

const TAKES = [
  "Restricts blood flow to gum tissue",
  "Accelerates collagen breakdown",
  "Triggers gum recession",
  "Stains, dehydrates, and irritates",
];

const GIVES = [
  "Floods gum tissue with collagen amino acids",
  "Delivers CoQ10 — depleted in periodontal cases",
  "Buffered to a gum-friendly pH 6.2–6.8",
  "Vitamin C cofactor for collagen synthesis",
];

export function Mechanism() {
  return (
    <section className="relative overflow-hidden bg-navy py-24 md:py-32">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 top-1/2 h-[420px] w-[420px] -translate-y-1/2 rounded-full bg-sky/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 md:px-10">
        <Reveal className="mb-14 max-w-3xl">
          <span className="eyebrow">Net zero damage</span>
          <h2 className="mt-4 font-serif text-4xl leading-[1.05] text-ivory md:text-6xl">
            Keep the ritual.
            <br />
            <span className="italic text-sky">Reverse the trade-off.</span>
          </h2>
          <p className="mt-6 max-w-xl text-base leading-relaxed text-ivory/70 md:text-lg">
            We&apos;re not telling you to quit. We&apos;re saying the same
            twenty-minute window that&apos;s costing you collagen can give it
            back.
          </p>
        </Reveal>

        <Reveal
          delay={120}
          className="relative grid overflow-hidden rounded-3xl border border-white/10 md:grid-cols-2"
        >
          <div className="relative bg-[#091226] p-8 md:p-12">
            <div className="text-[0.7rem] uppercase tracking-ultra-wide text-ivory/40">
              Nicotine takes
            </div>
            <ul className="mt-7 space-y-4">
              {TAKES.map((line) => (
                <li
                  key={line}
                  className="flex items-start gap-3 text-base text-ivory/45 line-through decoration-ivory/30 decoration-[1.5px] md:text-lg"
                >
                  <Minus />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="relative border-t border-white/10 bg-navy p-8 md:border-l md:border-t-0 md:p-12">
            <div className="text-[0.7rem] uppercase tracking-ultra-wide text-sky">
              Zibs gives back
            </div>
            <ul className="mt-7 space-y-4">
              {GIVES.map((line) => (
                <li
                  key={line}
                  className="flex items-start gap-3 text-base text-ivory md:text-lg"
                >
                  <Plus />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="pointer-events-none absolute left-1/2 top-1/2 hidden h-12 w-12 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full border border-white/10 bg-navy text-[0.6rem] uppercase tracking-ultra-wide text-sky md:flex">
            vs
          </div>
        </Reveal>

        <p className="mt-10 max-w-3xl text-sm leading-relaxed text-ivory/55 md:text-base">
          Same form factor. Same twenty-minute window. The active ingredients
          are doing the opposite job.
        </p>
      </div>
    </section>
  );
}

function Minus() {
  return (
    <span
      aria-hidden
      className="mt-2.5 inline-block h-px w-3.5 flex-shrink-0 bg-ivory/40"
    />
  );
}

function Plus() {
  return (
    <span
      aria-hidden
      className="relative mt-2 inline-block h-3.5 w-3.5 flex-shrink-0"
    >
      <span className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-sky" />
      <span className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-sky" />
    </span>
  );
}
