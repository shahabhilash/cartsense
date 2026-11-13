import { Heart, Plus } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { formatPrice, logEvent, type Product, type Reason } from "@/lib/api";
import { useCart } from "@/state/cart";
import { useWishlist } from "@/state/wishlist";
import { ProductArt } from "./ProductArt";
import { ReasonChip, ReasonList } from "./Reasons";

export { ReasonList } from "./Reasons";

export function ProductCard({
  product,
  reasons,
  impressionId,
}: {
  product: Product;
  reasons?: Reason[];
  impressionId?: string;
}) {
  const [open, setOpen] = useState(false);
  const wishlist = useWishlist();
  const cart = useCart();
  const saved = wishlist.ids.has(product.id);

  return (
    <article className="group relative flex flex-col rounded-2xl bg-surface p-3 shadow-card transition duration-300 hover:-translate-y-1 hover:shadow-lift">
      <div className="relative">
        <Link
          to={`/products/${product.id}${impressionId ? `?imp=${impressionId}` : ""}`}
          state={{ reasons }}
          onClick={() => logEvent({ event_type: "click", product_id: product.id, impression_id: impressionId })}
          aria-label={product.title}
        >
          <ProductArt product={product} />
        </Link>
        <button
          onClick={() => wishlist.toggle(product)}
          aria-label={saved ? "Remove from wishlist" : "Save to wishlist"}
          aria-pressed={saved}
          className="absolute right-2 top-2 flex h-8 w-8 items-center justify-center rounded-full bg-surface/90 text-ink shadow-sm backdrop-blur transition hover:scale-110"
        >
          <Heart size={15} className={saved ? "fill-brand text-brand" : ""} />
        </button>
        <button
          onClick={() => cart.add(product)}
          className="absolute bottom-2 right-2 flex h-8 items-center gap-1 rounded-full bg-brand px-3 text-xs font-medium text-canvas opacity-0 shadow-lift transition group-hover:opacity-100 focus:opacity-100"
        >
          <Plus size={13} /> Add
        </button>
      </div>

      <div className="mt-3 flex flex-1 flex-col">
        {reasons && reasons.length > 0 && (
          <div className="mb-1.5 flex flex-wrap gap-1">
            <ReasonChip reason={reasons[0]} />
          </div>
        )}
        <Link to={`/products/${product.id}`} state={{ reasons }} className="line-clamp-2 text-sm font-medium leading-snug hover:text-brand-dark">
          {product.title}
        </Link>
        <p className="mt-0.5 text-xs text-ink-muted">{product.brand ?? "Independent"}</p>
        <p className="mt-auto pt-2 text-sm font-semibold">{formatPrice(product.price)}</p>

        {reasons && reasons.length > 0 && (
          <>
            <button
              onClick={() => setOpen(!open)}
              className="mt-2 inline-flex items-center gap-1 self-start text-xs font-medium text-brand-dark hover:underline"
              aria-expanded={open}
            >
              {open ? "Hide" : "Why this?"}
            </button>
            {open && (
              <div className="mt-2 animate-fade-up">
                <ReasonList reasons={reasons} />
              </div>
            )}
          </>
        )}
      </div>
    </article>
  );
}

export function ProductCardSkeleton() {
  return (
    <div className="rounded-2xl bg-surface p-3 shadow-card" aria-hidden="true">
      <div className="relative aspect-square overflow-hidden rounded-xl bg-mist">
        <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-white/50 to-transparent" />
      </div>
      <div className="mt-3 h-3 w-4/5 rounded bg-mist" />
      <div className="mt-2 h-3 w-1/2 rounded bg-mist" />
      <div className="mt-4 h-3 w-1/4 rounded bg-mist" />
    </div>
  );
}
