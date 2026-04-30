"use client";

import { useEffect, useRef, useState } from "react";
import { Reveal } from "./Reveal";

const INGREDIENTS = [
  {
    index: "01",
    name: "Collagen Amino Acids",
    formula: "L-Glycine · L-Proline · L-Hydroxyproline",
    share: "18–28%",
    sharePct: 28,
    note: "Rate-limiting factors in gum tissue collagen synthesis.",
  },
  {
    index: "02",
    name: "HPMC Polymer",
    formula: "Medical-grade mucoadhesive · FDA GRAS",
    share: "15–20%",
    sharePct: 20,
    note: "Holds the pouch in place and controls timed release.",
  },
  {
    index: "03",
    name: "Vitamin C",
    formula: "Ascorbic acid",
    share: "3–5%",
    sharePct: 5,
    note: "Essential cofactor for collagen synthesis. Confirmed buccal absorption.",
  },
  {
    index: "04",
    name: "Coenzyme Q10",
    formula: "β-cyclodextrin encapsulated",
    share: "1–2%",
    sharePct: 2,
    note: "Documented deficient in periodontal tissue. Reduces pocket depth.",
  },
];

const MAX_SHARE = 30;

export function Ingredients() {
  const sectionRef = useRef<HTMLElement | null>(null);
  const [active, setActive] = useState(false);

  useEffect(() => {
    const node = sectionRef.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setActive(true);
      return;
    }
    const ob = new IntersectionObserver(
      (entries, obs) => {
        if (entries.some((e) => e.isIntersecting)) {
          setActive(true);
          obs.disconnect();
        }
      },
      { threshold: 0.2 }
    );
    ob.observe(node);
    return () => ob.disconnect();
  }, []);

  return (
    <section
      id="ingredients"
      ref={sectionRef}
      className="relative border-y border-white/5 bg-navy-deep"
    >
      <div className="mx-auto max-w-6xl px-6 py-24 md:px-10 md:py-32">
        <Reveal>
          <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
            <div>
              <span className="eyebrow">The formula</span>
              <h2 className="mt-4 max-w-xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
                Four actives.{" "}
                <span className="italic text-sky">No nicotine.</span>
              </h2>
            </div>
            <p className="max-w-md text-base leading-relaxed text-ivory/70">
              Buffered to a gum-friendly pH of 6.2–6.8. 400–500 mg per pouch.
              Engineered to release 60–80% of actives in the first half hour.
            </p>
          </div>
        </Reveal>

        <ul className="mt-14 divide-y divide-white/10 border-y border-white/10">
          {INGREDIENTS.map((ingredient, i) => (
            <Reveal as="li" key={ingredient.name} delay={80 * i}>
              <div className="grid grid-cols-[2.5rem_1fr] items-start gap-x-5 gap-y-3 py-8 md:grid-cols-[3rem_1.4fr_1.4fr_6rem] md:items-center md:gap-x-8">
                <span className="font-serif text-base text-sky md:text-lg">
                  {ingredient.index}
                </span>

                <div>
                  <h3 className="font-serif text-2xl text-ivory md:text-[1.85rem]">
                    {ingredient.name}
                  </h3>
                  <p className="mt-1 text-[0.7rem] uppercase tracking-ultra-wide text-sky">
                    {ingredient.formula}
                  </p>
                </div>

                <p className="col-start-2 text-sm leading-relaxed text-ivory/70 md:col-start-auto md:text-base">
                  {ingredient.note}
                </p>

                <div className="col-start-2 md:col-start-auto md:text-right">
                  <div className="font-serif text-2xl text-ivory md:text-3xl">
                    {ingredient.share}
                  </div>
                  <div className="mt-2 h-[3px] w-full overflow-hidden rounded-full bg-white/10 md:ml-auto md:max-w-[5rem]">
                    <div
                      className="h-full bg-sky transition-[width] duration-[900ms] ease-[cubic-bezier(0.22,0.61,0.36,1)]"
                      style={{
                        width: active
                          ? `${(ingredient.sharePct / MAX_SHARE) * 100}%`
                          : "0%",
                        transitionDelay: `${280 + i * 110}ms`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
