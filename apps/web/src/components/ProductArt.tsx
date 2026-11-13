import type { Product } from "@/lib/api";

// Product images are Amazon's and are off by default, so each product gets a
// generated "box art" tile: a palette per platform and a monogram from the title.

// Muted gradients per platform, in the same warm family as the UI
const PALETTES: Record<string, [string, string, string]> = {
  PC: ["#292524", "#44403C", "#E8B98A"],
  "Nintendo Switch": ["#5C1626", "#8E2A42", "#F9E6EA"],
  "PlayStation 4": ["#1E2A44", "#33476B", "#F5F5F4"],
  "PlayStation 5": ["#F4DEC1", "#FBEEDD", "#8A1538"],
  "Xbox One": ["#22382C", "#3B5A45", "#F5F5F4"],
  "Xbox Series X & S": ["#1F3326", "#365940", "#E8B98A"],
  "Legacy Systems": ["#9A6330", "#C68642", "#FFF7ED"],
};
const DEFAULT_PALETTE: [string, string, string] = ["#57534E", "#78716C", "#FAFAF9"];

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
      <div className="flex aspect-square items-center justify-center overflow-hidden rounded-xl bg-surface">
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
