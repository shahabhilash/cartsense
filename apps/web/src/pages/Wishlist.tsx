import { Heart } from "lucide-react";
import { Link } from "react-router-dom";
import { ProductCard } from "@/components/ProductCard";
import { EmptyState } from "@/components/Rail";
import { useAuth } from "@/state/auth";
import { useWishlist } from "@/state/wishlist";

export default function Wishlist() {
  const { user, ready } = useAuth();
  const { items } = useWishlist();

  if (!ready) return null;
  if (!user)
    return (
      <EmptyState icon={<Heart size={24} />} title="Save the things you love">
        <Link to="/login" className="font-medium text-brand-dark underline">Sign in</Link> to keep a wishlist. Saved items
        also shape your recommendations.
      </EmptyState>
    );

  return (
    <div>
      <p className="eyebrow">Saved for later</p>
      <h1 className="mt-1 text-4xl">Your wishlist</h1>
      <p className="mt-2 text-sm text-ink-muted">{items.length} {items.length === 1 ? "item" : "items"}</p>
      {items.length === 0 ? (
        <div className="mt-8">
          <EmptyState icon={<Heart size={24} />} title="Nothing saved yet">
            Tap the heart on any product. <Link to="/products" className="font-medium text-brand-dark underline">Browse the collection</Link>
          </EmptyState>
        </div>
      ) : (
        <div className="mt-8 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {items.map((p) => <ProductCard key={p.id} product={p} />)}
        </div>
      )}
    </div>
  );
}
