import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, type Product } from "@/lib/api";
import { useAuth } from "./auth";
import { useToast } from "./toast";

type WishlistApi = {
  ids: Set<string>;
  items: Product[];
  toggle: (product: Product) => Promise<void>;
  refresh: () => void;
};

const WishlistContext = createContext<WishlistApi>({
  ids: new Set(),
  items: [],
  toggle: async () => {},
  refresh: () => {},
});

export function WishlistProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { notify } = useToast();
  const [items, setItems] = useState<Product[]>([]);

  const refresh = useCallback(() => {
    if (!user) {
      setItems([]);
      return;
    }
    api<Product[]>("/me/wishlist").then(setItems).catch(() => setItems([]));
  }, [user]);

  useEffect(refresh, [refresh]);

  const toggle = useCallback(
    async (product: Product) => {
      if (!user) {
        notify("Sign in to save items to your wishlist", "info");
        return;
      }
      const saved = items.some((p) => p.id === product.id);
      // Optimistic update, rolled back if the API call fails
      setItems((cur) => (saved ? cur.filter((p) => p.id !== product.id) : [product, ...cur]));
      try {
        if (saved) await api(`/me/wishlist/${product.id}`, { method: "DELETE" });
        else await api("/me/wishlist", { method: "POST", body: JSON.stringify({ product_id: product.id }) });
        notify(saved ? "Removed from your wishlist" : "Saved to your wishlist");
      } catch (e) {
        refresh();
        notify((e as Error).message, "info");
      }
    },
    [items, notify, refresh, user],
  );

  return (
    <WishlistContext.Provider value={{ ids: new Set(items.map((p) => p.id)), items, toggle, refresh }}>
      {children}
    </WishlistContext.Provider>
  );
}

export const useWishlist = () => useContext(WishlistContext);
