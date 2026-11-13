import { ChevronRight, Heart, ShieldCheck, ShoppingBag, Sparkles, Star } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { ProductArt } from "@/components/ProductArt";
import { ProductCard } from "@/components/ProductCard";
import { ReasonList } from "@/components/Reasons";
import { Rail, RailItem, Section } from "@/components/Rail";
import { api, formatPrice, logEvent, type Product, type ProductDetail as Detail, type Reason } from "@/lib/api";
import { useCart } from "@/state/cart";
import { recentlyViewed, rememberViewed } from "@/state/recent";
import { useWishlist } from "@/state/wishlist";

function DetailSkeleton() {
  return (
    <div className="grid gap-10 lg:grid-cols-2" aria-hidden="true">
      <div className="aspect-square rounded-3xl bg-mist" />
      <div className="space-y-4">
        <div className="h-4 w-24 rounded bg-mist" />
        <div className="h-10 w-4/5 rounded bg-mist" />
        <div className="h-6 w-32 rounded bg-mist" />
        <div className="h-32 rounded bg-mist" />
      </div>
    </div>
  );
}

export default function ProductDetail() {
  const { id = "" } = useParams<{ id: string }>();
  const location = useLocation();
  const reasons = (location.state as { reasons?: Reason[] } | null)?.reasons ?? [];
  const [product, setProduct] = useState<Detail | null>(null);
  const [similar, setSimilar] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const cart = useCart();
  const wishlist = useWishlist();
  const saved = wishlist.ids.has(id);

  useEffect(() => {
    setProduct(null);
    setSimilar(null);
    setError(null);
    setExpanded(false);
    api<Detail>(`/products/${id}`)
      .then((p) => {
        setProduct(p);
        rememberViewed(p);
      })
      .catch((e) => setError(e.message));
    api<Product[]>(`/products/${id}/similar?k=10`).then(setSimilar).catch(() => setSimilar([]));
    logEvent({ event_type: "view", product_id: id });
    window.scrollTo({ top: 0 });
  }, [id]);

  if (error) return <p className="text-brand">{error}</p>;
  if (!product) return <DetailSkeleton />;

  const description = product.description ?? "";
  const recent = recentlyViewed(product.id);

  return (
    <div className="space-y-16">
      <div>
        <nav className="mb-6 flex items-center gap-1 text-xs text-ink-muted" aria-label="Breadcrumb">
          <Link to="/products" className="hover:text-ink">Shop</Link>
          <ChevronRight size={12} />
          {product.platform && (
            <>
              <Link to={`/products?platform=${encodeURIComponent(product.platform)}`} className="hover:text-ink">{product.platform}</Link>
              <ChevronRight size={12} />
            </>
          )}
          <span className="truncate text-ink">{product.title}</span>
        </nav>

        <div className="grid gap-10 lg:grid-cols-2">
          <div className="lg:sticky lg:top-36 lg:self-start">
            <div className="rounded-3xl bg-white p-4 shadow-card">
              <ProductArt product={product} size="lg" />
            </div>
          </div>

          <div>
            <p className="eyebrow">{product.brand ?? "Independent"}</p>
            <h1 className="mt-2 text-3xl leading-tight sm:text-4xl">{product.title}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-ink-muted">
              <span className="inline-flex items-center gap-1">
                <Star size={14} className="fill-brand text-brand" />
                {product.review_count.toLocaleString()} reviews
              </span>
              {product.popularity_rank && product.popularity_rank <= 500 && (
                <span className="rounded-full bg-brand/10 px-2.5 py-0.5 text-xs font-medium text-brand">
                  #{product.popularity_rank} trending
                </span>
              )}
              {product.release_date && <span>Released {new Date(product.release_date).getFullYear()}</span>}
            </div>

            <p className="mt-6 font-display text-3xl">{formatPrice(product.price)}</p>

            <div className="mt-6 flex flex-wrap gap-3">
              <button onClick={() => cart.add(product)} className="btn-primary flex-1 py-3 sm:flex-none sm:px-10">
                <ShoppingBag size={16} /> Add to bag
              </button>
              <button onClick={() => wishlist.toggle(product)} className="btn-outline py-3" aria-pressed={saved}>
                <Heart size={16} className={saved ? "fill-brand text-brand" : ""} />
                {saved ? "Saved" : "Save"}
              </button>
            </div>
            <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-ink-muted">
              <ShieldCheck size={13} /> Demo store: no real orders or payments.
            </p>

            {reasons.length > 0 && (
              <div className="mt-8 rounded-2xl border border-brand/30 bg-white p-4">
                <p className="mb-3 inline-flex items-center gap-1.5 text-sm font-semibold">
                  <Sparkles size={15} className="text-brand-dark" /> Why we recommended this
                </p>
                <ReasonList reasons={reasons} />
              </div>
            )}

            {product.features.length > 0 && (
              <div className="mt-8">
                <h2 className="text-xl">Highlights</h2>
                <ul className="mt-3 space-y-2">
                  {product.features.slice(0, 6).map((f, i) => (
                    <li key={i} className="flex gap-2 text-sm text-ink-soft">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand" />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {description && (
              <div className="mt-8">
                <h2 className="text-xl">About this item</h2>
                <p className="mt-3 whitespace-pre-line text-sm leading-relaxed text-ink-soft">
                  {expanded || description.length <= 500 ? description : `${description.slice(0, 500)}…`}
                </p>
                {description.length > 500 && (
                  <button onClick={() => setExpanded(!expanded)} className="mt-2 text-sm font-medium text-brand-dark hover:underline">
                    {expanded ? "Show less" : "Read more"}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {(similar === null || similar.length > 0) && (
        <Section eyebrow="You may also like" title="Similar products" subtitle="Matched on title, brand, platform and description.">
          <Rail loading={similar === null}>
            {similar?.map((p) => (
              <RailItem key={p.id}>
                <ProductCard
                  product={p}
                  reasons={[{ type: "similar_content", text: `Similar to “${product.title}” in title, brand and description` }]}
                />
              </RailItem>
            ))}
          </Rail>
        </Section>
      )}

      {recent.length > 0 && (
        <Section eyebrow="Your history" title="Recently viewed">
          <Rail>
            {recent.map((p) => (
              <RailItem key={p.id}>
                <ProductCard product={p} />
              </RailItem>
            ))}
          </Rail>
        </Section>
      )}
    </div>
  );
}
