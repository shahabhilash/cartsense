import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ProductCard } from "@/components/ProductCard";
import { api, type Product } from "@/lib/api";

type Page = { items: Product[]; total: number; page: number; page_size: number };

export default function Products() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Page | null>(null);
  const [error, setError] = useState<string | null>(null);
  const q = params.get("q") ?? "";
  const platform = params.get("platform") ?? "";
  const sort = params.get("sort") ?? "popular";
  const page = Number(params.get("page") ?? "1");

  useEffect(() => {
    const qs = new URLSearchParams({ sort, page: String(page), page_size: "24" });
    if (q) qs.set("q", q);
    if (platform) qs.set("platform", platform);
    setData(null);
    api<Page>(`/products?${qs}`).then(setData).catch((e) => setError(e.message));
  }, [q, platform, sort, page]);

  function go(update: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    Object.entries(update).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next);
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">
          {q ? `Results for "${q}"` : platform || "All products"}
          {data && <span className="ml-2 text-sm font-normal text-gray-500">{data.total.toLocaleString()} items</span>}
        </h1>
        <select value={sort} onChange={(e) => go({ sort: e.target.value, page: "1" })} aria-label="Sort"
          className="rounded border px-2 py-1 text-sm">
          <option value="popular">Most popular</option>
          <option value="newest">Newest</option>
          <option value="price_asc">Price: low to high</option>
          <option value="price_desc">Price: high to low</option>
        </select>
      </div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
        {data?.items.map((p) => <ProductCard key={p.id} product={p} />)}
      </div>
      {data && data.total === 0 && <p className="mt-6 text-gray-600">No products match.</p>}
      {data && pages > 1 && (
        <div className="mt-6 flex items-center gap-3 text-sm">
          <button disabled={page <= 1} onClick={() => go({ page: String(page - 1) })} className="disabled:text-gray-300">
            ← Previous
          </button>
          <span>Page {page} of {pages}</span>
          <button disabled={page >= pages} onClick={() => go({ page: String(page + 1) })} className="disabled:text-gray-300">
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
