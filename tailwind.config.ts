import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: "#0d1f3c",
        "navy-deep": "#091633",
        "navy-soft": "#142a52",
        sky: "#a8c4e0",
        "sky-soft": "#c8dbef",
        ivory: "#f5f1e8",
      },
      fontFamily: {
        serif: ["var(--font-cormorant)", "Cormorant Garamond", "serif"],
        sans: ["var(--font-dm-sans)", "DM Sans", "system-ui", "sans-serif"],
      },
      letterSpacing: {
        "ultra-wide": "0.32em",
      },
      boxShadow: {
        soft: "0 30px 60px -30px rgba(0, 0, 0, 0.55)",
      },
    },
  },
  plugins: [],
};

export default config;
