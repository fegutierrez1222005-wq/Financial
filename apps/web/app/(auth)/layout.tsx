import Link from "next/link";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-ink-950">
      <header className="border-b border-ink-800">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <Link href="/" className="font-mono text-sm font-semibold tracking-[0.2em] text-ink-100 no-underline">
            FINAGENT&nbsp;LAB
          </Link>
        </div>
      </header>
      <main className="flex flex-1 items-center justify-center px-6 py-14">
        <div className="w-full max-w-md">{children}</div>
      </main>
      <footer className="border-t border-ink-800 px-6 py-5">
        <p className="mx-auto max-w-6xl text-2xs text-ink-500">
          Customer data is isolated and is not used for model training unless explicitly
          authorized.
        </p>
      </footer>
    </div>
  );
}
