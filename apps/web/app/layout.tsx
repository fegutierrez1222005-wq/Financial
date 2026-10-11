import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "FINAGENT LAB — evaluation and observability for institutional financial AI",
    template: "%s · FINAGENT LAB",
  },
  description:
    "Build financial research agents, capture every action they take, score them against a " +
    "golden dataset, and backtest the ideas under explicit cost and execution-lag assumptions.",
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
