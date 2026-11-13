import type { Product } from "@/lib/api";

// Product images are Amazon's and are off by default, so each product gets a
// generated "box art" tile: a palette per platform and a monogram from the title.

const PALETTES: Record<string, [string, string, string]> = {
  PC: ["#2B2621", "#4A4036", "#D7B48A"],
  "Nintendo Switch": ["#8E1B26", "#B23A3F", "#F3EDE3"],
  "PlayStation 4": ["#1F2A3A", "#3A4B63", "#E9DFCF"],
  "PlayStation 5": ["#E9DFCF", "#FAF7F2", "#1B1814"],
  "Xbox One": ["#2E3B2C", "#4C5E46", "#E9DFCF"],
  "Xbox Series X & S": ["#24301F", "#3E5135", "#D7B48A"],
  "Legacy Systems": ["#8C6239", "#B88A5A", "#FAF7F2"],
};
const DEFAULT_PALETTE: [string, string, string] = ["#B88A5A", "#D7B48A", "#1B1814"];

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
      <span className={`font-serif ${text} font-semibold tracking-wide`}>{monogram(product.title)}</span>
      {size !== "sm" && (
        <span className="absolute bottom-3 left-0 right-0 text-center text-[10px] font-semibold uppercase tracking-[0.25em] opacity-80">
          {product.platform ?? "Video Games"}
        </span>
      )}
    </div>
  );
}
