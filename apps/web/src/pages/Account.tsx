import { User } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ProductArt } from "@/components/ProductArt";
import { EmptyState } from "@/components/Rail";
import { api, type Product } from "@/lib/api";
import { useAuth } from "@/state/auth";
import { useWishlist } from "@/state/wishlist";

type HistoryItem = { product: Product; rating: number; occurred_at: string };

export default function Account() {
  const { user, ready } = useAuth();
  const { items: saved } = useWishlist();
  const [history, setHistory] = useState<HistoryItem[] | null>(null);

  useEffect(() => {
    if (user) api<HistoryItem[]>("/me/history?limit=30").then(setHistory).catch(() => setHistory([]));
  }, [user]);

  if (!ready) return null;
  if (!user)
    return (
      <EmptyState icon={<User size={24} />} title="Your account">
        <Link to="/login" className="font-medium text-brand-dark underline">Sign in</Link> to see your profile.
      </EmptyState>
    );

  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center gap-5 rounded-3xl bg-surface p-6 shadow-card">
        <span className="flex h-16 w-16 items-center justify-center rounded-full bg-brand font-display text-2xl text-canvas">
          {user.display_name.slice(0, 1).toUpperCase()}
        </span>
        <div>
          <p className="eyebrow">{user.is_demo ? "Demo shopper from the dataset" : "Member"}</p>
          <h1 className="mt-1 text-3xl">{user.display_name}</h1>
          {user.email && <p className="text-sm text-ink-muted">{user.email}</p>}
        </div>
        <dl className="ml-auto flex gap-6 text-center">
          <div><dt className="text-xs text-ink-muted">Recent reviews</dt><dd className="font-display text-2xl">{history?.length ?? "–"}</dd></div>
          <div><dt className="text-xs text-ink-muted">Saved</dt><dd className="font-display text-2xl">{saved.length}</dd></div>
        </dl>
      </div>

      <section>
        <h2 className="text-2xl">Your reviews</h2>
        <p className="mt-1 text-sm text-ink-muted">
          {user.is_demo
            ? "Real reviews from this shopper in the dataset. The recommender learned from these."
            : "Products you review will appear here. Until then, recommendations follow what you browse and save."}
        </p>
        {history && history.length === 0 && <p className="mt-6 text-sm text-ink-muted">No reviews yet.</p>}
        <ul className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {history?.map((h) => (
            <li key={h.product.id + h.occurred_at}>
              <Link to={`/products/${h.product.id}`} className="flex gap-3 rounded-2xl bg-surface p-3 shadow-card transition hover:shadow-lift">
                <div className="w-16 shrink-0"><ProductArt product={h.product} size="sm" /></div>
                <div className="min-w-0">
                  <p className="line-clamp-2 text-sm font-medium">{h.product.title}</p>
                  <p className="mt-1 text-xs font-semibold text-brand">Rated {h.rating}/5</p>
                  <p className="mt-0.5 text-xs text-ink-muted">{new Date(h.occurred_at).toLocaleDateString()}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
