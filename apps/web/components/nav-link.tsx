"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function NavLink({ href, children }: { href: string; children: React.ReactNode }) {
  const pathname = usePathname();
  const active = pathname === href || pathname.startsWith(`${href}/`);

  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={`inline-block border-b-2 px-3 py-2.5 text-sm no-underline transition-colors ${
        active
          ? "border-signal-info text-ink-100"
          : "border-transparent text-ink-400 hover:text-ink-200"
      }`}
    >
      {children}
    </Link>
  );
}
