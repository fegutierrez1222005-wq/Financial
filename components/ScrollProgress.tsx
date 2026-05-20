"use client";

import { useEffect, useState } from "react";

/**
 * Fixed 2px progress bar at the very top of the viewport that tracks how far
 * down the page the user has scrolled. Stays under the sticky nav so it reads
 * as a thin sky-blue line filling left → right.
 */
export function ScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let raf = 0;
    const update = () => {
      const doc = document.documentElement;
      const max = doc.scrollHeight - doc.clientHeight;
      const value = max <= 0 ? 0 : doc.scrollTop / max;
      setProgress(Math.max(0, Math.min(1, value)));
      raf = 0;
    };

    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      aria-hidden
      className="pointer-events-none fixed left-0 right-0 top-0 z-[60] h-[2px]"
    >
      <div
        style={{ transform: `scaleX(${progress})` }}
        className="h-full origin-left bg-gradient-to-r from-sky/40 via-sky to-sky/60 transition-transform duration-100 ease-linear"
      />
    </div>
  );
}
