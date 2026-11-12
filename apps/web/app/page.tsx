"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProductCard } from "@/components/ProductCard";
import { api, getToken, type RecList } from "@/lib/api";

const STRATEGY_LABEL: Record<RecList["strategy"], string> = {
  precomputed: "Recommended for you",
  session_similarity: "Based on what you browsed",
  popular: "Trending now",
};

export default function Home() {
  const [recs, setRecs] = useState<RecList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [platforms, setPlatforms] = useState<{ platform: string; products: number }[]>([]);

  useEffect(() => {
    api<RecList>("/recommendations?k=12&surface=home").then(setRecs).catch((e) => setError(e.message));
    api<{ platform: string; products: number }[]>("/platforms").then(setPlatforms).catch(() => {});
  }, []);

  return (
    <div className="space-y-8">
      <section>
        <div className="flex items-baseline justify-between">
          <h1 className="text-xl font-semibold">{recs ? STRATEGY_LABEL[recs.strategy] : "Loading…"}</h1>
          {recs && <span className="text-xs text-gray-500">model: {recs.model_version}</span>}
        </div>
        {!getToken() && (
          <p className="mt-1 text-sm text-gray-600">
            <Link href="/login" className="text-indigo-700 underline">Sign in or try a demo shopper</Link> to see
            personal recommendations.
          </p>
        )}
        {error && <p className="mt-3 text-sm text-red-600">Could not load recommendations: {error}</p>}
        <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
          {recs?.items.map((r) => (
            <ProductCard key={r.product.id} product={r.product} reasons={r.reasons} impressionId={r.impression_id} />
          ))}
        </div>
      </section>
      <section>
        <h2 className="text-lg font-semibold">Shop by platform</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {platforms.map((p) => (
            <Link key={p.platform} href={`/products?platform=${encodeURIComponent(p.platform)}`}
              className="rounded-full border bg-white px-3 py-1 text-sm hover:bg-gray-50">
              {p.platform} <span className="text-gray-400">({p.products})</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
