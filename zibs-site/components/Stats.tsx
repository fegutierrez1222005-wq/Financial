const STATS = [
  {
    figure: "47%",
    label: "of US adults",
    description: "live with some form of gum disease right now.",
  },
  {
    figure: "20 min",
    label: "daily contact",
    description:
      "between cheek and gum line — sustained release while you go about your day.",
  },
  {
    figure: "30 ct",
    label: "per tin",
    description:
      "a full month of routine. One pouch a day. Subscribe and forget.",
  },
];

export function Stats() {
  return (
    <section className="border-y border-white/5 bg-navy-deep">
      <div className="mx-auto grid max-w-6xl gap-px bg-white/5 px-0 md:grid-cols-3">
        {STATS.map((stat) => (
          <div
            key={stat.figure}
            className="bg-navy-deep px-8 py-14 md:px-10 md:py-16"
          >
            <div className="font-serif text-6xl text-ivory md:text-7xl">
              {stat.figure}
            </div>
            <div className="mt-3 text-xs uppercase tracking-ultra-wide text-sky">
              {stat.label}
            </div>
            <p className="mt-5 max-w-xs text-base leading-relaxed text-ivory/70">
              {stat.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
