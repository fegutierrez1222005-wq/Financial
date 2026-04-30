"use client";

import { useState } from "react";

const ITEMS = [
  {
    q: "What's actually in a Zibs pouch?",
    a: "Each 400–500 mg pouch is built around four actives: collagen amino acids (L-glycine, L-proline, L-hydroxyproline) at 18–28%, β-cyclodextrin-encapsulated CoQ10 at 1–2%, Vitamin C at 3–5%, and medical-grade HPMC mucoadhesive polymer at 15–20%. Buffered to pH 6.2–6.8 so it's gentle on gum tissue.",
  },
  {
    q: "How is this different from a Zyn?",
    a: "Same form factor, same tin, same twenty-minute ritual. No nicotine, no tobacco. Where nicotine restricts blood flow and accelerates collagen breakdown, Zibs delivers the rate-limiting cofactors gum tissue needs to rebuild — straight through the buccal membrane.",
  },
  {
    q: "How long do I keep it in?",
    a: "Twenty to thirty minutes. The mucoadhesive HPMC mesh holds the pouch flush against your gum line for sustained release; pulling it earlier just wastes actives. Most users settle into one pouch a day.",
  },
  {
    q: "Is it FDA approved?",
    a: "Zibs is regulated as a dietary supplement, not a drug. FDA drug approval isn't required to launch a product in this category. We are independently pursuing the ADA Seal of Acceptance and have an NIDCR SBIR clinical study planned.",
  },
  {
    q: "Will it make my gums worse?",
    a: "Zibs is engineered for the opposite: gum-friendly pH, no acidic flavor systems, no nicotine, and no added sugar. Every active in the formula has documented use in oral tissue.",
  },
  {
    q: "Is it patented?",
    a: "USPTO Provisional Patent Application filed April 21, 2026. Full utility application in progress.",
  },
];

export function FAQ() {
  return (
    <section
      id="faq"
      className="relative border-y border-white/5 bg-navy-deep py-24 md:py-32"
    >
      <div className="mx-auto max-w-4xl px-6 md:px-10">
        <div className="mb-12 text-center">
          <span className="eyebrow">Questions</span>
          <h2 className="mt-4 font-serif text-4xl leading-tight text-ivory md:text-5xl">
            Research-backed <span className="italic text-sky">answers.</span>
          </h2>
        </div>

        <ul className="divide-y divide-white/10 border-y border-white/10">
          {ITEMS.map((item, index) => (
            <FAQItem
              key={item.q}
              question={item.q}
              answer={item.a}
              defaultOpen={index === 0}
            />
          ))}
        </ul>
      </div>
    </section>
  );
}

function FAQItem({
  question,
  answer,
  defaultOpen = false,
}: {
  question: string;
  answer: string;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <li>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-start justify-between gap-6 py-6 text-left transition hover:text-ivory"
      >
        <span className="font-serif text-xl text-ivory md:text-2xl">
          {question}
        </span>
        <span
          aria-hidden
          className={`relative mt-2 inline-block h-3 w-3 flex-shrink-0 transition-transform duration-200 ${
            open ? "rotate-45" : ""
          }`}
        >
          <span className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-sky" />
          <span className="absolute left-0 top-1/2 h-px w-full -translate-y-1/2 bg-sky" />
        </span>
      </button>
      {open && (
        <p className="-mt-1 max-w-3xl pb-7 pr-8 text-base leading-relaxed text-ivory/70">
          {answer}
        </p>
      )}
    </li>
  );
}
