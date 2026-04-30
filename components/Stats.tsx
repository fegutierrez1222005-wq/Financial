const SECONDARY = [
  { figure: "20–30 min", label: "Buccal contact time" },
  { figure: "30 ct", label: "Pouches per tin" },
  { figure: "0 mg", label: "Nicotine in formula" },
];

export function Stats() {
  return (
    <section className="relative overflow-hidden border-y border-white/5 bg-navy-deep">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -right-32 top-1/2 h-[420px] w-[420px] -translate-y-1/2 rounded-full bg-sky/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-6 py-24 md:px-10 md:py-28">
        <div className="grid items-end gap-12 md:grid-cols-[1.1fr_1fr] md:gap-16">
          <div>
            <div className="eyebrow">The problem</div>
            <div className="mt-6 flex items-end gap-5">
              <div className="font-serif text-[7rem] leading-[0.85] text-ivory md:text-[10rem]">
                47<span className="text-sky">%</span>
              </div>
              <div className="pb-3 text-xs uppercase tracking-ultra-wide text-sky">
                of US
                <br />
                adults
              </div>
            </div>
            <p className="mt-7 max-w-md text-base leading-relaxed text-ivory/65 md:text-lg">
              live with some form of periodontal disease right now, per the CDC.
              Most don&apos;t know yet — gum recession is silent until it
              isn&apos;t.
            </p>
          </div>

          <ul className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/5 sm:grid-cols-3 md:max-w-md md:grid-cols-1">
            {SECONDARY.map((stat) => (
              <li
                key={stat.label}
                className="flex items-baseline justify-between bg-navy-deep px-6 py-5"
              >
                <span className="font-serif text-2xl text-ivory md:text-3xl">
                  {stat.figure}
                </span>
                <span className="text-[0.65rem] uppercase tracking-ultra-wide text-ivory/55">
                  {stat.label}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
