import type { Product } from "@/lib/api";

// Product images are Amazon's and are off by default, so each product gets a
// generated "box art" tile: a palette per platform and a monogram from the title.

// Muted gradients per platform, on the same slate/indigo scale as the UI
const PALETTES: Record<string, [string, string, string]> = {
  PC: ["#1E293B", "#334155", "#E2E8F0"],
  "Nintendo Switch": ["#BE123C", "#E11D48", "#FFF1F2"],
  "PlayStation 4": ["#1E3A8A", "#2563EB", "#EFF6FF"],
  "PlayStation 5": ["#E2E8F0", "#F8FAFC", "#1E3A8A"],
  "Xbox One": ["#065F46", "#059669", "#ECFDF5"],
  "Xbox Series X & S": ["#14532D", "#16A34A", "#F0FDF4"],
  "Legacy Systems": ["#4338CA", "#7C3AED", "#EEF2FF"],
};
const DEFAULT_PALETTE: [string, string, string] = ["#475569", "#64748B", "#F8FAFC"];

const STOP_WORDS = new Set(["the", "a", "an", "of", "and", "for", "with", "edition", "standard"]);

export function monogram(title: string): string {
  const words = title
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .split(/\s+/)
    .filter((w) => w && !STOP_WORDS.has(w.toLowerCase()));
  return (words.slice(0, 2).map((w) => w[0]).join("") || "CS").toUpperCase();
}

export function ProductArt({ product, size = "md" }: { product: Product; size?: "sm" | "md" | "lg" }) {
  if (product.image_url) {
    return (
      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-xl bg-white">
        <img src={product.image_url} alt="" className="h-full w-full object-contain p-4" loading="lazy" />
      </div>
    );
  }
  const [from, to, fg] = PALETTES[product.platform ?? ""] ?? DEFAULT_PALETTE;
  const text = size === "lg" ? "text-7xl" : size === "sm" ? "text-2xl" : "text-4xl";
  return (
    <div
      className="relative flex aspect-square items-center justify-center overflow-hidden rounded-xl"
      style={{ background: `linear-gradient(145deg, ${from}, ${to})`, color: fg }}
      aria-hidden="true"
    >
      <div className="absolute inset-3 rounded-lg border" style={{ borderColor: `${fg}33` }} />
      <span className={`font-display ${text} font-extrabold tracking-tight`}>{monogram(product.title)}</span>
      {size !== "sm" && (
        <span className="absolute bottom-3 left-0 right-0 text-center text-[10px] font-semibold uppercase tracking-[0.25em] opacity-80">
          {product.platform ?? "Video Games"}
        </span>
      )}
    </div>
  );
}
