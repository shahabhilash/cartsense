import { ChevronLeft, ChevronRight, SearchX, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ProductCard, ProductCardSkeleton } from "@/components/ProductCard";
import { EmptyState } from "@/components/Rail";
import { api, type Product } from "@/lib/api";

type Page = { items: Product[]; total: number; page: number; page_size: number };

const SORTS = [
  ["popular", "Most popular"],
  ["newest", "Newest"],
  ["price_asc", "Price: low to high"],
  ["price_desc", "Price: high to low"],
] as const;

export default function Products() {
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState<Page | null>(null);
  const [platforms, setPlatforms] = useState<{ platform: string; products: number }[]>([]);
  const [error, setError] = useState<string | null>(null);
  const q = params.get("q") ?? "";
  const platform = params.get("platform") ?? "";
  const sort = params.get("sort") ?? "popular";
  const page = Number(params.get("page") ?? "1");

  useEffect(() => {
    api<{ platform: string; products: number }[]>("/platforms").then(setPlatforms).catch(() => {});
  }, []);

  useEffect(() => {
    const qs = new URLSearchParams({ sort, page: String(page), page_size: "24" });
    if (q) qs.set("q", q);
    if (platform) qs.set("platform", platform);
    setData(null);
    setError(null);
    api<Page>(`/products?${qs}`).then(setData).catch((e) => setError(e.message));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [q, platform, sort, page]);

  function go(update: Record<string, string>) {
    const next = new URLSearchParams(params.toString());
    Object.entries(update).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next);
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const title = q ? `“${q}”` : platform || (sort === "newest" ? "New in" : "The collection");

  return (
    <div>
      <div className="border-b border-mist pb-6">
        <p className="eyebrow">{q ? "Search results" : "Shop"}</p>
        <h1 className="mt-1 text-4xl">{title}</h1>
        {data && <p className="mt-2 text-sm text-ink-muted">{data.total.toLocaleString()} products</p>}
      </div>

      <div className="mt-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:flex-wrap sm:px-0">
          <button
            onClick={() => go({ platform: "", page: "1" })}
            className={`shrink-0 rounded-full border px-4 py-1.5 text-sm transition ${!platform ? "border-ink bg-ink text-canvas" : "border-mist-deep bg-white hover:border-ink"}`}
          >
            All
          </button>
          {platforms.slice(0, 8).map((p) => (
            <button
              key={p.platform}
              onClick={() => go({ platform: p.platform, page: "1" })}
              className={`shrink-0 rounded-full border px-4 py-1.5 text-sm transition ${platform === p.platform ? "border-ink bg-ink text-canvas" : "border-mist-deep bg-white hover:border-ink"}`}
            >
              {p.platform}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3">
          {(q || platform) && (
            <button onClick={() => go({ q: "", platform: "", page: "1" })} className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-ink">
              <X size={13} /> Clear filters
            </button>
          )}
          <select value={sort} onChange={(e) => go({ sort: e.target.value, page: "1" })} aria-label="Sort"
            className="rounded-full border border-mist-deep bg-white px-4 py-2 text-sm focus:border-brand focus:outline-none">
            {SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </div>
      </div>

      {error && <p className="mt-6 text-sm text-accent">{error}</p>}

      <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
        {data
          ? data.items.map((p) => <ProductCard key={p.id} product={p} />)
          : !error && Array.from({ length: 10 }, (_, i) => <ProductCardSkeleton key={i} />)}
      </div>

      {data && data.total === 0 && (
        <div className="mt-6">
          <EmptyState icon={<SearchX size={24} />} title="Nothing matches yet">
            Try a shorter search, another platform, or clear the filters.
          </EmptyState>
        </div>
      )}

      {data && pages > 1 && (
        <nav className="mt-10 flex items-center justify-center gap-4 text-sm" aria-label="Pagination">
          <button disabled={page <= 1} onClick={() => go({ page: String(page - 1) })} className="btn-outline px-3 py-2">
            <ChevronLeft size={16} /> Previous
          </button>
          <span className="text-ink-muted">Page {page} of {pages.toLocaleString()}</span>
          <button disabled={page >= pages} onClick={() => go({ page: String(page + 1) })} className="btn-outline px-3 py-2">
            Next <ChevronRight size={16} />
          </button>
        </nav>
      )}
    </div>
  );
}
