const PARTNERS = [
  { name: "USPTO", note: "Provisional patent" },
  { name: "Northwestern", note: "Founder & research" },
  { name: "Quarles & Brady", note: "IP counsel" },
  { name: "ADA", note: "Seal pursuit" },
  { name: "NIDCR", note: "SBIR track" },
];

export function PartnerStrip() {
  return (
    <section className="border-y border-white/5 bg-navy-deep">
      <div className="mx-auto max-w-6xl px-6 py-12 md:px-10 md:py-14">
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center gap-3">
            <span className="hidden h-px w-10 bg-white/15 md:block" />
            <span className="text-[0.7rem] uppercase tracking-ultra-wide text-sky">
              Backed by
            </span>
            <span className="hidden h-px w-10 bg-white/15 md:block" />
          </div>
        </div>

        <ul className="mt-8 grid grid-cols-2 gap-x-6 gap-y-7 sm:grid-cols-3 md:grid-cols-5">
          {PARTNERS.map((partner) => (
            <li
              key={partner.name}
              className="flex flex-col items-center text-center"
            >
              <div className="font-serif text-xl text-ivory md:text-[1.65rem]">
                {partner.name}
              </div>
              <div className="mt-1 text-[0.6rem] uppercase tracking-ultra-wide text-ivory/45">
                {partner.note}
              </div>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
