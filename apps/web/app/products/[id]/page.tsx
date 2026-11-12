"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ProductCard, ProductThumb } from "@/components/ProductCard";
import { api, formatPrice, getToken, logEvent, type Product, type ProductDetail } from "@/lib/api";

export default function ProductPage() {
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [similar, setSimilar] = useState<Product[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [wished, setWished] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    api<ProductDetail>(`/products/${id}`).then(setProduct).catch((e) => setError(e.message));
    api<Product[]>(`/products/${id}/similar?k=6`).then(setSimilar).catch(() => {});
    logEvent({ event_type: "view", product_id: id });
    if (getToken()) {
      api<Product[]>("/me/wishlist").then((w) => setWished(w.some((p) => p.id === id))).catch(() => {});
    }
  }, [id]);

  async function toggleWishlist() {
    if (!getToken()) {
      setMessage("Sign in to use the wishlist.");
      return;
    }
    try {
      if (wished) await api(`/me/wishlist/${id}`, { method: "DELETE" });
      else await api("/me/wishlist", { method: "POST", body: JSON.stringify({ product_id: id }) });
      setWished(!wished);
    } catch (e) {
      setMessage((e as Error).message);
    }
  }

  if (error) return <p className="text-red-600">{error}</p>;
  if (!product) return <p>Loading…</p>;
  return (
    <div className="space-y-8">
      <div className="grid gap-6 md:grid-cols-[280px_1fr]">
        <ProductThumb product={product} />
        <div>
          <h1 className="text-2xl font-semibold">{product.title}</h1>
          <p className="text-gray-600">
            {product.brand} · {product.platform}
          </p>
          <p className="mt-2 text-xl font-semibold">{formatPrice(product.price)}</p>
          <p className="text-sm text-gray-500">{product.review_count.toLocaleString()} reviews in the dataset</p>
          <button
            onClick={toggleWishlist}
            className="mt-3 rounded bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700"
          >
            {wished ? "♥ In wishlist" : "♡ Add to wishlist"}
          </button>
          {message && <p className="mt-2 text-sm text-gray-600">{message}</p>}
          {product.features.length > 0 && (
            <ul className="mt-4 list-disc space-y-1 pl-5 text-sm">
              {product.features.slice(0, 6).map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          )}
          {product.description && (
            <p className="mt-4 whitespace-pre-line text-sm text-gray-700">{product.description.slice(0, 1200)}</p>
          )}
        </div>
      </div>
      {similar.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold">Similar products</h2>
          <div className="mt-3 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            {similar.map((p) => (
              <ProductCard
                key={p.id}
                product={p}
                reasons={[{ type: "similar_content", text: `Similar to "${product.title}" (title, brand and description)` }]}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
