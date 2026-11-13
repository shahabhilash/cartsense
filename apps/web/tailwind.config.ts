import type { Config } from "tailwindcss";

// Beige backgrounds and surfaces, a crisp red as the strong colour, sand accents
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#2B211C", soft: "#4E413A", muted: "#6F6157" },
        canvas: { DEFAULT: "#F3ECE1", deep: "#EDE3D3" },
        surface: "#FBF7F0",
        mist: { DEFAULT: "#EDE3D3", deep: "#DCCBB1" },
        brand: { light: "#F7B5C0", DEFAULT: "#C8102E", dark: "#9B0C23" },
        accent: { light: "#EAD9BF", DEFAULT: "#C9A97E", dark: "#A88658" },
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(60,40,25,0.05), 0 8px 24px -12px rgba(60,40,25,0.18)",
        lift: "0 2px 4px rgba(60,40,25,0.06), 0 18px 40px -16px rgba(60,40,25,0.30)",
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
