import type { Config } from "tailwindcss";

// "Heritage" palette: camel, ink black, ivory and an oxblood accent
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#1B1814", soft: "#3A342D", muted: "#6F665B" },
        ivory: { DEFAULT: "#FAF7F2", deep: "#F3EDE3" },
        sand: { DEFAULT: "#E9DFCF", deep: "#D9C9AF" },
        camel: { light: "#D7B48A", DEFAULT: "#B88A5A", dark: "#8C6239" },
        oxblood: { DEFAULT: "#8E1B26", dark: "#6E141D" },
      },
      fontFamily: {
        serif: ['"Playfair Display"', "Georgia", "serif"],
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(27,24,20,0.04), 0 8px 24px -12px rgba(27,24,20,0.18)",
        lift: "0 2px 4px rgba(27,24,20,0.06), 0 18px 40px -16px rgba(27,24,20,0.30)",
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
