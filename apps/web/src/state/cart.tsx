import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { logEvent, type Product } from "@/lib/api";
import { readJSON, writeJSON } from "./storage";
import { useToast } from "./toast";

// The cart lives in the browser: the store is a demo and takes no payments.
// Adding an item is still logged as an add_to_cart event for the recommender.

export type CartLine = { product: Product; quantity: number };

type CartApi = {
  lines: CartLine[];
  count: number;
  subtotal: number;
  open: boolean;
  setOpen: (open: boolean) => void;
  add: (product: Product) => void;
  setQuantity: (productId: string, quantity: number) => void;
  remove: (productId: string) => void;
  clear: () => void;
};

const KEY = "cartsense_cart";
const CartContext = createContext<CartApi | null>(null);

export function CartProvider({ children }: { children: ReactNode }) {
  const { notify } = useToast();
  const [lines, setLines] = useState<CartLine[]>(() => readJSON<CartLine[]>(KEY, []));
  const [open, setOpen] = useState(false);

  useEffect(() => writeJSON(KEY, lines), [lines]);

  const add = useCallback(
    (product: Product) => {
      setLines((cur) => {
        const found = cur.find((l) => l.product.id === product.id);
        return found
          ? cur.map((l) => (l.product.id === product.id ? { ...l, quantity: Math.min(l.quantity + 1, 9) } : l))
          : [...cur, { product, quantity: 1 }];
      });
      logEvent({ event_type: "add_to_cart", product_id: product.id });
      notify(`Added to bag: ${product.title.slice(0, 40)}${product.title.length > 40 ? "…" : ""}`);
      setOpen(true);
    },
    [notify],
  );

  const setQuantity = useCallback((productId: string, quantity: number) => {
    setLines((cur) =>
      quantity <= 0
        ? cur.filter((l) => l.product.id !== productId)
        : cur.map((l) => (l.product.id === productId ? { ...l, quantity: Math.min(quantity, 9) } : l)),
    );
  }, []);

  const remove = useCallback((productId: string) => setLines((cur) => cur.filter((l) => l.product.id !== productId)), []);
  const clear = useCallback(() => setLines([]), []);

  const value = useMemo(() => {
    const count = lines.reduce((n, l) => n + l.quantity, 0);
    const subtotal = lines.reduce((s, l) => s + (l.product.price ?? 0) * l.quantity, 0);
    return { lines, count, subtotal, open, setOpen, add, setQuantity, remove, clear };
  }, [lines, open, add, setQuantity, remove, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartApi {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used inside CartProvider");
  return ctx;
}
