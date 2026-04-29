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

  const setQuantity = useCallback((next: number) => {
    setQuantityState(Math.max(0, Math.min(99, Math.floor(next))));
  }, []);

  const addToCart = useCallback(() => {
    setQuantityState((q) => Math.min(99, q + 1));
    setIsOpen(true);
  }, []);

  const removeOne = useCallback(() => {
    setQuantityState((q) => Math.max(0, q - 1));
  }, []);

  const value = useMemo<CartContextValue>(
    () => ({
      quantity,
      isOpen,
      addToCart,
      removeOne,
      setQuantity,
      openCart: () => setIsOpen(true),
      closeCart: () => setIsOpen(false),
    }),
    [quantity, isOpen, addToCart, removeOne, setQuantity]
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
