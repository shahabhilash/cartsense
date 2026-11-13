import type { Product } from "@/lib/api";
import { readJSON, writeJSON } from "./storage";

const KEY = "cartsense_recently_viewed";
const MAX = 12;

export function rememberViewed(product: Product): void {
  const current = readJSON<Product[]>(KEY, []).filter((p) => p.id !== product.id);
  writeJSON(KEY, [product, ...current].slice(0, MAX));
}

export function recentlyViewed(excludeId?: string): Product[] {
  return readJSON<Product[]>(KEY, []).filter((p) => p.id !== excludeId);
}
