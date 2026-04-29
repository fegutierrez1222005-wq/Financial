const INGREDIENTS = [
  {
    name: "Collagen Amino Acids",
    formula: "L-Glycine · L-Proline · L-Hydroxyproline",
    share: "18–28%",
    note: "Rate-limiting factors in gum tissue collagen synthesis.",
  },
  {
    name: "Coenzyme Q10",
    formula: "β-cyclodextrin encapsulated",
    share: "1–2%",
    note: "Documented deficient in periodontal tissue. Reduces pocket depth.",
  },
  {
    name: "Vitamin C",
    formula: "Ascorbic acid",
    share: "3–5%",
    note: "Essential cofactor for collagen synthesis. Confirmed buccal absorption.",
  },
  {
    name: "HPMC Polymer",
    formula: "Medical-grade mucoadhesive · FDA GRAS",
    share: "15–20%",
    note: "Holds the pouch in place and controls timed release.",
  },
];

export function Ingredients() {
  return (
    <section
      id="ingredients"
      className="relative border-y border-white/5 bg-navy-deep"
    >
      <div className="mx-auto max-w-6xl px-6 py-24 md:px-10 md:py-32">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="eyebrow">The formula</span>
            <h2 className="mt-4 max-w-xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
              Four actives. <span className="italic text-sky">No nicotine.</span>
            </h2>
          </div>
          <p className="max-w-md text-base leading-relaxed text-ivory/70">
            Buffered to a gum-friendly pH of 6.2–6.8. 400–500 mg per pouch.
            Engineered to release 60–80% of actives in the first half hour.
          </p>
        </div>

        <ul className="mt-14 divide-y divide-white/10 border-y border-white/10">
          {INGREDIENTS.map((ingredient) => (
            <li
              key={ingredient.name}
              className="grid grid-cols-1 items-center gap-2 py-7 md:grid-cols-[1.1fr_1.4fr_0.5fr] md:gap-8"
            >
              <div>
                <h3 className="font-serif text-2xl text-ivory md:text-3xl">
                  {ingredient.name}
                </h3>
                <p className="mt-1 text-xs uppercase tracking-ultra-wide text-sky">
                  {ingredient.formula}
                </p>
              </div>
              <p className="text-sm leading-relaxed text-ivory/70 md:text-base">
                {ingredient.note}
              </p>
              <div className="font-serif text-3xl text-ivory/90 md:text-right md:text-4xl">
                {ingredient.share}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
