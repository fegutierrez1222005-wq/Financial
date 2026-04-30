const COLUMNS = [
  {
    heading: "Product",
    links: [
      { label: "How it works", href: "#how-it-works" },
      { label: "Ingredients", href: "#ingredients" },
      { label: "Spec sheet", href: "#specs" },
      { label: "Reserve", href: "#reserve" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "FAQ", href: "#faq" },
      { label: "Patent status", href: "#faq" },
      { label: "Contact", href: "mailto:hi@zibs.com" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative border-t border-white/10 bg-[#04091a]">
      <div className="mx-auto max-w-6xl px-6 py-16 md:px-10 md:py-20">
        <div className="grid gap-12 md:grid-cols-[1.6fr_1fr_1fr]">
          <div>
            <div className="font-serif text-3xl text-ivory">Zibs</div>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-ivory/55">
              Zero nicotine. Dietary supplement. A buccal pouch that gives back
              what nicotine takes from your gums.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 text-[0.6rem] uppercase tracking-ultra-wide text-ivory/45">
              <span className="rounded-full border border-white/10 px-3 py-1">
                Patent Pending
              </span>
              <span className="rounded-full border border-white/10 px-3 py-1">
                USPTO · 04 / 2026
              </span>
              <span className="rounded-full border border-white/10 px-3 py-1">
                Northwestern
              </span>
            </div>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.heading}>
              <div className="text-[0.65rem] uppercase tracking-ultra-wide text-sky">
                {col.heading}
              </div>
              <ul className="mt-5 space-y-3 text-sm text-ivory/70">
                {col.links.map((link) => (
                  <li key={link.label}>
                    <a
                      href={link.href}
                      className="transition hover:text-ivory"
                    >
                      {link.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col gap-3 border-t border-white/10 pt-6 text-[0.65rem] uppercase tracking-ultra-wide text-ivory/40 md:flex-row md:items-center md:justify-between">
          <span>© Zibs 2026 · All rights reserved</span>
          <span className="md:text-right">
            These statements have not been evaluated by the FDA. Not intended
            to diagnose, treat, cure, or prevent any disease.
          </span>
        </div>
      </div>
    </footer>
  );
}
