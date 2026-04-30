"use client";

import { useEffect, useRef, useState } from "react";
import { Reveal } from "./Reveal";

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
          <Reveal>
            <div className="eyebrow">The problem</div>

            <div className="mt-6 flex items-end gap-2">
              <CountUp
                target={47}
                className="font-serif text-[6.5rem] leading-none tracking-[-0.04em] text-ivory md:text-[9.5rem]"
              />
              <span className="font-serif text-[4.5rem] leading-none tracking-[-0.04em] text-sky md:text-[6.5rem]">
                %
              </span>
            </div>

            <div className="mt-5 text-[0.65rem] uppercase tracking-ultra-wide text-sky">
              of US adults · CDC, 2024
            </div>

            <p className="mt-6 max-w-md text-base leading-relaxed text-ivory/65 md:text-lg">
              live with some form of periodontal disease right now. Most
              don&apos;t know yet — gum recession is silent until it
              isn&apos;t.
            </p>
          </Reveal>

          <Reveal delay={120}>
            <ul className="grid gap-px overflow-hidden rounded-2xl border border-white/10 bg-white/5">
              {SECONDARY.map((stat, i) => (
                <li
                  key={stat.label}
                  className="flex items-center justify-between bg-navy-deep px-7 py-6"
                  style={{
                    animation: `fade-in-row 600ms ${
                      i * 90 + 200
                    }ms cubic-bezier(0.22,0.61,0.36,1) both`,
                  }}
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
          </Reveal>
        </div>
      </div>
    </section>
  );
}

function CountUp({
  target,
  className,
}: {
  target: number;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement | null>(null);
  const [value, setValue] = useState(0);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setValue(target);
      return;
    }
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduce) {
      setValue(target);
      return;
    }

    const observer = new IntersectionObserver(
      (entries, obs) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        const start = performance.now();
        const duration = 1100;
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / duration);
          // easeOutCubic
          const eased = 1 - Math.pow(1 - t, 3);
          setValue(Math.round(eased * target));
          if (t < 1) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        obs.disconnect();
      },
      { threshold: 0.4 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [target]);

  return (
    <span ref={ref} className={className} aria-label={`${target} percent`}>
      {value}
    </span>
  );
}
