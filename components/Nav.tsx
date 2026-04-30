"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useCart } from "./CartProvider";

export function Nav() {
  const { quantity, openCart, bumpKey } = useCart();
  const [isBumping, setIsBumping] = useState(false);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    setIsBumping(true);
    const timer = window.setTimeout(() => setIsBumping(false), 360);
    return () => window.clearTimeout(timer);
  }, [bumpKey]);

  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-navy/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5 md:px-10">
        <Link href="/" className="flex items-center gap-3">
          <span className="font-serif text-2xl tracking-tight text-ivory">
            Zibs
          </span>
          <span className="hidden text-[0.6rem] uppercase tracking-ultra-wide text-sky sm:inline">
            Patent Pending
          </span>
        </Link>
        <nav className="hidden items-center gap-7 text-sm text-ivory/70 md:flex">
          <a href="#how-it-works" className="hover:text-ivory">
            How it works
          </a>
          <a href="#ingredients" className="hover:text-ivory">
            Ingredients
          </a>
          <a href="#reserve" className="hover:text-ivory">
            Reserve
          </a>
          <a href="#faq" className="hover:text-ivory">
            FAQ
          </a>
        </nav>

        <button
          type="button"
          onClick={openCart}
          aria-label={`Open cart (${quantity} item${quantity === 1 ? "" : "s"})`}
          className={`group relative inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm font-medium text-ivory transition hover:border-sky/40 hover:bg-white/10 ${
            isBumping ? "cart-button-bump" : ""
          }`}
        >
          <CartIcon />
          <span className="hidden sm:inline">Cart</span>
          <span
            className={`flex h-5 min-w-[1.25rem] items-center justify-center rounded-full px-1.5 text-[0.7rem] font-semibold leading-none transition ${
              quantity > 0
                ? "bg-sky text-navy"
                : "bg-white/10 text-ivory/60 group-hover:bg-white/15"
            } ${isBumping ? "cart-badge-bump" : ""}`}
          >
            {quantity}
          </span>
        </button>
      </div>
    </header>
  );
}

function CartIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden
    >
      <path d="M3 4h2l2.5 12.5a2 2 0 0 0 2 1.5h8a2 2 0 0 0 2-1.6L21 8H6" />
      <circle cx="10" cy="20.5" r="1.2" />
      <circle cx="17" cy="20.5" r="1.2" />
    </svg>
  );
}
