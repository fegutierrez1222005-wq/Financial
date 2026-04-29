export function Footer() {
  return (
    <footer className="border-t border-white/5 bg-navy-deep">
      <div className="mx-auto flex max-w-6xl flex-col gap-6 px-6 py-12 md:flex-row md:items-center md:justify-between md:px-10">
        <div>
          <div className="font-serif text-2xl text-ivory">Zibs</div>
          <p className="mt-2 max-w-md text-sm text-ivory/55">
            Zero nicotine. Dietary supplement. For the generation that
            won&apos;t quit the pouch — but won&apos;t lose its face to it
            either.
          </p>
        </div>
        <div className="flex flex-col items-start gap-1 text-xs uppercase tracking-ultra-wide text-ivory/45 md:items-end">
          <span>Patent Pending · USPTO</span>
          <span>April 2026</span>
          <span>© Zibs 2026 · All rights reserved</span>
        </div>
      </div>
    </footer>
  );
}
