import type { Config } from "tailwindcss";

// Slate + indigo palette: neutral surfaces, one brand colour, one sparing accent
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#0F172A", soft: "#334155", muted: "#64748B" },
        canvas: { DEFAULT: "#F8FAFC", deep: "#F1F5F9" },
        mist: { DEFAULT: "#E2E8F0", deep: "#CBD5E1" },
        brand: { light: "#A5B4FC", DEFAULT: "#4F46E5", dark: "#4338CA" },
        accent: { DEFAULT: "#E11D48", dark: "#BE123C" },
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(15,23,42,0.04), 0 8px 24px -12px rgba(15,23,42,0.14)",
        lift: "0 2px 4px rgba(15,23,42,0.05), 0 18px 40px -16px rgba(15,23,42,0.25)",
      },
      keyframes: {
        shimmer: { "100%": { transform: "translateX(100%)" } },
        "slide-in": { from: { transform: "translateX(100%)" }, to: { transform: "translateX(0)" } },
        "fade-up": { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        shimmer: "shimmer 1.4s infinite",
        "slide-in": "slide-in 0.25s ease-out",
        "fade-up": "fade-up 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};
export default config;
