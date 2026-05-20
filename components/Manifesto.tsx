import { Reveal } from "./Reveal";

/**
 * A single high-contrast editorial band placed between Mechanism and Stats.
 * Inverts the navy palette (ivory background, navy text) so the eye gets a
 * breath in the middle of an otherwise dark page. No testimonials, just a
 * one-sentence thesis with a small attribution.
 */
export function Manifesto() {
  return (
    <section className="relative overflow-hidden bg-ivory text-navy">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -left-32 top-1/2 h-[420px] w-[420px] -translate-y-1/2 rounded-full bg-sky/20 blur-3xl" />
        <div className="absolute -right-24 bottom-0 h-[300px] w-[300px] rounded-full bg-navy/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-4xl px-6 py-28 md:px-10 md:py-36">
        <Reveal>
          <div className="flex items-center gap-3">
            <span className="h-px w-10 bg-navy/30" />
            <span className="text-[0.7rem] uppercase tracking-ultra-wide text-navy/55">
              The premise
            </span>
          </div>
        </Reveal>

        <Reveal delay={80}>
          <p className="mt-8 font-serif text-[2.25rem] leading-[1.1] tracking-[-0.01em] text-navy md:text-[3.4rem]">
            <span aria-hidden className="text-sky/70">
              &ldquo;
            </span>
            Same form factor.
            <br className="hidden sm:block" />
            <span className="italic">Opposite biochemistry.</span>
            <span aria-hidden className="text-sky/70">
              &rdquo;
            </span>
          </p>
        </Reveal>

        <Reveal delay={160}>
          <p className="mt-10 max-w-2xl text-base leading-relaxed text-navy/70 md:text-lg">
            Zibs started from one question: what if the twenty minutes a day
            you&apos;re already giving to a pouch could rebuild gum tissue
            instead of strip it? Every decision in the formula — pH, fill
            weight, mucoadhesive polymer, rate-limiting cofactors — is
            engineered against that single goal.
          </p>
        </Reveal>

        <Reveal delay={220}>
          <div className="mt-10 flex items-center gap-4 text-[0.7rem] uppercase tracking-ultra-wide text-navy/50">
            <span className="h-px w-8 bg-navy/30" />
            <span>Fernando Gutierrez · Founder</span>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
