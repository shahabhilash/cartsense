import type { Config } from "tailwindcss";

// Caramel backgrounds and surfaces, clean wine red as the strong colour
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#2A1712", soft: "#4B2E22", muted: "#5E4030" },
        canvas: { DEFAULT: "#E2B47E", deep: "#EBCDA6" },
        surface: "#F4DEC1",
        mist: { DEFAULT: "#EAC9A0", deep: "#D19E66" },
        brand: { light: "#F4B6C7", DEFAULT: "#8A1538", dark: "#6B0F2A" },
        accent: { light: "#F8D2A0", DEFAULT: "#B8732F", dark: "#8F5520" },
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(74,40,20,0.06), 0 8px 24px -12px rgba(74,40,20,0.22)",
        lift: "0 2px 4px rgba(74,40,20,0.08), 0 18px 40px -16px rgba(74,40,20,0.35)",
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
