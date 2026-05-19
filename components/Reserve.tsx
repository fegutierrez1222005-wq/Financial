"use client";

import { formatPrice, PRODUCT, useCart } from "./CartProvider";
import { Reveal } from "./Reveal";
import { Tin } from "./Tin";

const FEATURES = [
  "30 mucoadhesive pouches",
  "Zero nicotine · Dietary supplement",
  "Collagen amino acids · CoQ10 · Vitamin C",
  "20–30 minute sustained release",
];

export function Reserve() {
  const { quantity, addToCart, openCart } = useCart();

  return (
    <section
      id="reserve"
      className="relative overflow-hidden bg-navy py-24 md:py-32"
    >
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute left-1/2 top-1/2 h-[520px] w-[520px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-sky/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-5xl px-6 md:px-10">
        <Reveal>
          <div className="mb-12 text-center">
            <span className="eyebrow">Reserve</span>
            <h2 className="mt-4 font-serif text-4xl leading-tight text-ivory md:text-5xl">
              One tin. <span className="italic text-sky">One ritual.</span>
            </h2>
          </div>
        </Reveal>

        <Reveal
          delay={120}
          className="grid overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] shadow-[0_40px_80px_-40px_rgba(0,0,0,0.6)] backdrop-blur-sm transition-all duration-500 hover:border-sky/20 md:grid-cols-[1.05fr_1fr]"
        >
          <div className="relative flex items-center justify-center bg-navy-deep px-6 py-12 md:px-10 md:py-16">
            <div className="absolute inset-0 bg-gradient-to-br from-sky/10 via-transparent to-transparent" />
            <Tin className="relative h-72 w-72 max-w-full md:h-80 md:w-80" />
          </div>

          <div className="flex flex-col gap-7 p-8 md:p-10">
            <div>
              <div className="flex items-center justify-between">
                <div className="text-[0.7rem] uppercase tracking-ultra-wide text-sky">
                  {PRODUCT.description}
                </div>
                <span className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-[0.6rem] uppercase tracking-ultra-wide text-ivory/55">
                  Pre-launch
                </span>
              </div>
              <h3 className="mt-3 font-serif text-3xl text-ivory md:text-[2.4rem]">
                {PRODUCT.name}
              </h3>
              <div className="mt-3 flex items-baseline gap-2">
                <span className="font-serif text-4xl text-ivory md:text-5xl">
                  {formatPrice(PRODUCT.priceCents)}
                </span>
                <span className="text-base text-ivory/45">/ tin</span>
              </div>
            </div>

            <ul className="grid grid-cols-2 gap-3 border-t border-white/10 pt-5 text-sm text-ivory/75">
              {FEATURES.map((feature) => (
                <li
                  key={feature}
                  className="flex items-start gap-2.5 leading-snug"
                >
                  <span
                    aria-hidden
                    className="mt-1.5 h-1 w-2.5 flex-shrink-0 bg-sky"
                  />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>

            <div className="mt-auto space-y-2.5">
              <button
                type="button"
                onClick={addToCart}
                className="w-full rounded-full bg-sky px-6 py-3.5 text-sm font-semibold text-navy transition hover:bg-sky-soft"
              >
                Add to cart · {formatPrice(PRODUCT.priceCents)}
              </button>

              {quantity > 0 && (
                <button
                  type="button"
                  onClick={openCart}
                  className="w-full rounded-full border border-white/10 px-6 py-3 text-sm font-medium text-ivory/80 transition hover:border-sky/40 hover:bg-white/5"
                >
                  View cart ({quantity})
                </button>
              )}

              <p className="pt-1 text-center text-[0.65rem] uppercase tracking-ultra-wide text-ivory/40">
                Adjust quantity in cart · No charge today
              </p>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

