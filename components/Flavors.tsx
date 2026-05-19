import { Reveal } from "./Reveal";
import { Tin } from "./Tin";

const FLAVORS = [
  {
    id: "wintergreen",
    name: "Wintergreen",
    note: "Cool, classic, gum-friendly",
    palette: "navy" as const,
    caption: "WINTERGREEN · 30 CT",
    glow: "from-sky/25 via-sky/5 to-transparent",
  },
  {
    id: "cool-mint",
    name: "Cool Mint",
    note: "Crisp peppermint, low sweetness",
    palette: "mint" as const,
    caption: "COOL MINT · 30 CT",
    glow: "from-emerald-300/20 via-teal-300/10 to-transparent",
  },
  {
    id: "citrus",
    name: "Citrus",
    note: "Bright, Vitamin-C forward",
    palette: "citrus" as const,
    caption: "CITRUS · 30 CT",
    glow: "from-amber-300/25 via-orange-300/10 to-transparent",
  },
];

export function Flavors() {
  return (
    <section className="relative overflow-hidden bg-navy py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6 md:px-10">
        <div className="mb-12 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <span className="eyebrow">Flavors</span>
            <h2 className="mt-4 max-w-xl font-serif text-4xl leading-tight text-ivory md:text-5xl">
              Three at launch.
              <br />
              <span className="italic text-sky">More on the way.</span>
            </h2>
          </div>
          <p className="max-w-md text-base leading-relaxed text-ivory/65">
            Same formula in every tin. Flavor systems chosen for low acidity,
            no added sugar, and no irritants — the whole point is being kind to
            your gums.
          </p>
        </div>

        <ul className="grid gap-6 md:grid-cols-3">
          {FLAVORS.map((flavor, index) => (
            <Reveal
              as="li"
              delay={index * 100}
              key={flavor.id}
              className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.03] p-7 transition-all duration-500 hover:-translate-y-1 hover:border-sky/30 hover:shadow-[0_30px_60px_-30px_rgba(168,196,224,0.25)]"
            >
              <div
                className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${flavor.glow} opacity-70 transition group-hover:opacity-100`}
              />
              <div className="relative flex h-56 items-center justify-center transition-transform duration-500 group-hover:-translate-y-1">
                <Tin
                  palette={flavor.palette}
                  caption={flavor.caption}
                  className="h-full w-full"
                  ariaLabel={`${flavor.name} Zibs tin`}
                />
              </div>
              <div className="relative mt-6 flex items-end justify-between">
                <div>
                  <h3 className="font-serif text-2xl text-ivory">
                    {flavor.name}
                  </h3>
                  <p className="mt-1 text-sm text-ivory/60">{flavor.note}</p>
                </div>
                <span className="rounded-full border border-white/15 px-3 py-1 text-[0.6rem] uppercase tracking-ultra-wide text-ivory/55">
                  Coming soon
                </span>
              </div>
            </Reveal>
          ))}
        </ul>
      </div>
    </section>
  );
}
