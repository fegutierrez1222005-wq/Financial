"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
} from "react";

export const PRODUCT = {
  id: "zibs-tin-30",
  name: "Zibs Tin",
  description: "30 mucoadhesive pouches · zero nicotine",
  priceCents: 3999,
};

type CartContextValue = {
  quantity: number;
  isOpen: boolean;
  bumpKey: number;
  addToCart: () => void;
  removeOne: () => void;
  setQuantity: (next: number) => void;
  openCart: () => void;
  closeCart: () => void;
};

const CartContext = createContext<CartContextValue | null>(null);

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [quantity, setQuantityState] = useState(0);
  const [isOpen, setIsOpen] = useState(false);
  // Increments every time an item is added so the nav can play a brief
  // bump animation as feedback. Keeps the drawer closed until the user
  // explicitly opens it.
  const [bumpKey, setBumpKey] = useState(0);

  const setQuantity = useCallback((next: number) => {
    setQuantityState(Math.max(0, Math.min(99, Math.floor(next))));
  }, []);

  const addToCart = useCallback(() => {
    setQuantityState((q) => Math.min(99, q + 1));
    setBumpKey((k) => k + 1);
  }, []);

  const removeOne = useCallback(() => {
    setQuantityState((q) => Math.max(0, q - 1));
  }, []);

  const value = useMemo<CartContextValue>(
    () => ({
      quantity,
      isOpen,
      bumpKey,
      addToCart,
      removeOne,
      setQuantity,
      openCart: () => setIsOpen(true),
      closeCart: () => setIsOpen(false),
    }),
    [quantity, isOpen, bumpKey, addToCart, removeOne, setQuantity]
  );

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) {
    throw new Error("useCart must be used within a CartProvider");
  }
  return ctx;
}

export function formatPrice(cents: number) {
  return `$${(cents / 100).toFixed(2)}`;
}
