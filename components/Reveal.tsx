"use client";

import { useEffect, useRef, useState } from "react";

type RevealProps = {
  children: React.ReactNode;
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li";
};

export function Reveal({
  children,
  delay = 0,
  className = "",
  as: Tag = "div",
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (typeof IntersectionObserver === "undefined") {
      setShown(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setShown(true);
            observer.disconnect();
          }
        });
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.05 }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  const refCallback = (node: HTMLElement | null) => {
    ref.current = node;
  };

  const props = {
    ref: refCallback,
    style: shown && delay ? { transitionDelay: `${delay}ms` } : undefined,
    className: `reveal ${shown ? "reveal-in" : ""} ${className}`.trim(),
  };

  return (
    <Tag {...(props as React.HTMLAttributes<HTMLElement> & { ref: typeof refCallback })}>
      {children}
    </Tag>
  );
}
