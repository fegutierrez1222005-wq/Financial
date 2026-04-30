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
        <div className="grid items-center gap-14 md:grid-cols-[1.05fr_1fr] md:gap-16">
          <div>
            <div className="eyebrow">The problem</div>
            <div className="mt-6 leading-none">
              <span className="font-serif text-[7rem] tracking-[-0.04em] text-ivory md:text-[10rem]">
                47
              </span>
              <span className="font-serif text-[5rem] tracking-[-0.04em] text-sky md:text-[7rem]">
                %
              </span>
            </div>
            <div className="-mt-2 text-xs uppercase tracking-ultra-wide text-sky">
              of US adults · CDC, 2024
            </div>
            <p className="mt-7 max-w-md text-base leading-relaxed text-ivory/65 md:text-lg">
              live with some form of periodontal disease right now. Most
              don&apos;t know yet — gum recession is silent until it isn&apos;t.
            </p>
          </div>

          <ul className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/5">
            {SECONDARY.map((stat) => (
              <li
                key={stat.label}
                className="flex items-center justify-between bg-navy-deep px-7 py-6"
              >
                <span className="text-[0.65rem] uppercase tracking-ultra-wide text-ivory/55">
                  {stat.label}
                </span>
                <span className="font-serif text-3xl text-ivory md:text-[2.25rem]">
                  {stat.figure}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
