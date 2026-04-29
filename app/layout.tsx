import type { Metadata } from "next";
import { Cormorant_Garamond, DM_Sans } from "next/font/google";
import { CartProvider } from "@/components/CartProvider";
import "./globals.css";

const cormorant = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-cormorant",
  display: "swap",
});

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-dm-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Zibs — Keep the pouch. Lose the damage.",
  description:
    "Zibs is a zero-nicotine buccal pouch that delivers collagen amino acids, CoQ10, and Vitamin C straight to the gum line. Patent pending.",
  metadataBase: new URL("https://zibs.com"),
  openGraph: {
    title: "Zibs — Keep the pouch. Lose the damage.",
    description:
      "Zero-nicotine buccal pouch. 20 minutes a day. Collagen amino acids, CoQ10, Vitamin C.",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Zibs — Keep the pouch. Lose the damage.",
    description:
      "Zero-nicotine buccal pouch. Collagen amino acids, CoQ10, Vitamin C. Patent pending.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${cormorant.variable} ${dmSans.variable}`}>
      <body>
        <CartProvider>{children}</CartProvider>
      </body>
    </html>
  );
}
