"use client";

import { useEffect, useState } from "react";
import { formatPrice, PRODUCT, useCart } from "./CartProvider";
import { Tin } from "./Tin";

type Status = "idle" | "loading" | "success" | "error";

export function CartDrawer() {
  const { isOpen, closeCart, quantity, addToCart, removeOne } = useCart();
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    if (!isOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeCart();
    };
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [isOpen, closeCart]);

  useEffect(() => {
    if (!isOpen) {
      setStatus("idle");
      setErrorMessage("");
    }
  }, [isOpen]);

  const subtotal = quantity * PRODUCT.priceCents;

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "loading") return;
    if (quantity === 0) return;

    setStatus("loading");
    setErrorMessage("");

    try {
      const response = await fetch("/api/waitlist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, quantity }),
      });
      const data = (await response
        .json()
        .catch(() => ({}))) as { error?: string };
      if (!response.ok) {
        throw new Error(data.error ?? "Something went wrong. Try again.");
      }
      setStatus("success");
      setEmail("");
    } catch (error) {
      setStatus("error");
      setErrorMessage(
        error instanceof Error
          ? error.message
          : "Something went wrong. Try again."
      );
    }
  }

  return (
    <div
      aria-hidden={!isOpen}
      className={`fixed inset-0 z-50 ${
        isOpen ? "pointer-events-auto" : "pointer-events-none"
      }`}
    >
      <div
        onClick={closeCart}
        className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ${
          isOpen ? "opacity-100" : "opacity-0"
        }`}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Cart"
        className={`absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-white/10 bg-navy-deep shadow-soft transition-transform duration-300 sm:max-w-md ${
          isOpen ? "translate-x-0" : "translate-x-full"
        }`}
      >
        <header className="flex items-center justify-between border-b border-white/10 px-6 py-5">
          <div>
            <div className="eyebrow">Your cart</div>
            <div className="mt-1 font-serif text-2xl text-ivory">
              {quantity === 0
                ? "Empty"
                : `${quantity} item${quantity === 1 ? "" : "s"}`}
            </div>
          </div>
          <button
            type="button"
            onClick={closeCart}
            aria-label="Close cart"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-white/10 text-ivory/70 transition hover:border-sky/40 hover:text-ivory"
          >
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
              <path d="M6 6l12 12M18 6L6 18" />
            </svg>
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-6">
          {quantity === 0 ? (
            <EmptyCart />
          ) : (
            <CartLine
              quantity={quantity}
              onIncrease={addToCart}
              onDecrease={removeOne}
            />
          )}
        </div>

        <footer className="border-t border-white/10 bg-navy px-6 py-6">
          <div className="flex items-center justify-between text-sm text-ivory/70">
            <span className="uppercase tracking-ultra-wide text-[0.7rem]">
              Subtotal
            </span>
            <span className="font-serif text-2xl text-ivory">
              {formatPrice(subtotal)}
            </span>
          </div>

          {status === "success" ? (
            <SuccessState />
          ) : (
            <form onSubmit={handleSubmit} className="mt-5 space-y-3">
              <label
                htmlFor="cart-email"
                className="block text-[0.7rem] uppercase tracking-ultra-wide text-sky"
              >
                Email for reservation updates
              </label>
              <input
                id="cart-email"
                type="email"
                required
                autoComplete="email"
                inputMode="email"
                placeholder="you@school.edu"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                disabled={quantity === 0}
                className="w-full rounded-full border border-white/15 bg-white/5 px-5 py-3 text-base text-ivory placeholder-ivory/40 outline-none transition focus:border-sky focus:bg-white/10 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={status === "loading" || quantity === 0}
                className="w-full rounded-full bg-sky px-6 py-3 text-sm font-semibold text-navy transition hover:bg-sky-soft disabled:cursor-not-allowed disabled:opacity-50"
              >
                {quantity === 0
                  ? "Cart is empty"
                  : status === "loading"
                  ? "Reserving…"
                  : `Reserve · ${formatPrice(subtotal)}`}
              </button>
              {status === "error" && (
                <p className="text-center text-sm text-red-300">
                  {errorMessage}
                </p>
              )}
              <p className="pt-1 text-center text-[0.65rem] uppercase tracking-ultra-wide text-ivory/40">
                No charge today · Pre-launch reservation
              </p>
            </form>
          )}
        </footer>
      </aside>
    </div>
  );
}

function CartLine({
  quantity,
  onIncrease,
  onDecrease,
}: {
  quantity: number;
  onIncrease: () => void;
  onDecrease: () => void;
}) {
  return (
    <div className="flex gap-4">
      <div className="flex h-24 w-24 flex-shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/10 bg-navy">
        <Tin shadow={false} caption="30 CT" className="h-full w-full" />
      </div>
      <div className="flex-1">
        <div className="font-serif text-xl text-ivory">{PRODUCT.name}</div>
        <div className="mt-1 text-xs uppercase tracking-ultra-wide text-sky">
          {PRODUCT.description}
        </div>
        <div className="mt-3 flex items-center justify-between">
          <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-1.5 py-1">
            <button
              type="button"
              onClick={onDecrease}
              aria-label="Decrease quantity"
              className="flex h-7 w-7 items-center justify-center rounded-full text-ivory/70 transition hover:bg-white/10 hover:text-ivory"
            >
              −
            </button>
            <span className="min-w-[1.25rem] text-center text-sm text-ivory">
              {quantity}
            </span>
            <button
              type="button"
              onClick={onIncrease}
              aria-label="Increase quantity"
              className="flex h-7 w-7 items-center justify-center rounded-full text-ivory/70 transition hover:bg-white/10 hover:text-ivory"
            >
              +
            </button>
          </div>
          <div className="font-serif text-lg text-ivory">
            {formatPrice(PRODUCT.priceCents * quantity)}
          </div>
        </div>
      </div>
    </div>
  );
}

function EmptyCart() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center">
      <div className="text-sky/70">
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.4"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="mx-auto h-10 w-10"
          aria-hidden
        >
          <path d="M3 4h2l2.5 12.5a2 2 0 0 0 2 1.5h8a2 2 0 0 0 2-1.6L21 8H6" />
          <circle cx="10" cy="20.5" r="1.2" />
          <circle cx="17" cy="20.5" r="1.2" />
        </svg>
      </div>
      <p className="mt-4 max-w-xs text-sm text-ivory/60">
        Your cart is empty. Add a Zibs tin to reserve yours.
      </p>
    </div>
  );
}

function SuccessState() {
  return (
    <div className="mt-5 rounded-2xl border border-sky/30 bg-sky/10 p-5 text-left">
      <div className="font-serif text-2xl text-ivory">Reservation saved.</div>
      <p className="mt-2 text-sm leading-relaxed text-ivory/75">
        We&apos;ll email you when Zibs ships.
      </p>
    </div>
  );
}

