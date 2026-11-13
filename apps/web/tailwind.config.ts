import type { Config } from "tailwindcss";

// Wine red brand, caramel accent, warm stone neutrals
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1C1917", soft: "#44403C", muted: "#78716C" },
        canvas: { DEFAULT: "#FAFAF9", deep: "#F5F5F4" },
        mist: { DEFAULT: "#E7E5E4", deep: "#D6D3D1" },
        brand: { light: "#E7A1B0", DEFAULT: "#7B1E34", dark: "#5C1626" },
        accent: { light: "#E8B98A", DEFAULT: "#C68642", dark: "#9A6330" },
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', "Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(28,25,23,0.04), 0 8px 24px -12px rgba(28,25,23,0.16)",
        lift: "0 2px 4px rgba(28,25,23,0.05), 0 18px 40px -16px rgba(28,25,23,0.28)",
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
