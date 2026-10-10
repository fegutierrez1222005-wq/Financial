import type { Config } from "tailwindcss";

/**
 * Institutional research terminal, not a consumer SaaS marketing site:
 * dense, high-contrast, monospace numerals, restrained colour used only to carry meaning.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#07090c",
          900: "#0b0e13",
          850: "#10141b",
          800: "#161b24",
          700: "#1f2632",
          600: "#2b3342",
          500: "#3d4859",
          400: "#5c6879",
          300: "#8792a3",
          200: "#b7c0cd",
          100: "#dfe4ec",
        },
        signal: {
          positive: "#2f9e6d",
          negative: "#d2504b",
          caution: "#c8922f",
          info: "#4b7bd2",
          mock: "#8d6bd4",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        "2xs": ["0.6875rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        sm: "2px",
        DEFAULT: "3px",
        md: "4px",
        lg: "6px",
      },
    },
  },
  plugins: [],
};

export default config;
