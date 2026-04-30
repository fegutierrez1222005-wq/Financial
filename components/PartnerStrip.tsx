const PARTNERS = [
  "USPTO",
  "Northwestern",
  "Quarles & Brady",
  "ADA Seal pursuit",
  "NIDCR SBIR track",
];

export function PartnerStrip() {
  return (
    <section className="border-y border-white/5 bg-navy-deep">
      <div className="mx-auto max-w-6xl px-6 py-10 md:px-10 md:py-12">
        <div className="text-center text-[0.7rem] uppercase tracking-ultra-wide text-sky">
          Backed by
        </div>
        <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-5 md:gap-x-14">
          {PARTNERS.map((partner) => (
            <li
              key={partner}
              className="font-serif text-xl text-ivory/70 md:text-2xl"
            >
              {partner}
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
