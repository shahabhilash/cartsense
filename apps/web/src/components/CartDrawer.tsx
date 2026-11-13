import { Minus, Plus, ShoppingBag, Trash2, X } from "lucide-react";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { formatPrice } from "@/lib/api";
import { useCart, type CartLine } from "@/state/cart";
import { ProductArt } from "./ProductArt";

export function CartLineRow({ line }: { line: CartLine }) {
  const cart = useCart();
  const { product, quantity } = line;
  return (
    <li className="flex gap-3 py-4">
      <Link to={`/products/${product.id}`} onClick={() => cart.setOpen(false)} className="w-20 shrink-0">
        <ProductArt product={product} size="sm" />
      </Link>
      <div className="flex min-w-0 flex-1 flex-col">
        <Link to={`/products/${product.id}`} onClick={() => cart.setOpen(false)} className="line-clamp-2 text-sm font-medium hover:text-brand-dark">
          {product.title}
        </Link>
        <p className="text-xs text-ink-muted">{product.platform}</p>
        <div className="mt-auto flex items-center justify-between pt-2">
          <div className="flex items-center rounded-full border border-mist-deep">
            <button onClick={() => cart.setQuantity(product.id, quantity - 1)} className="p-1.5" aria-label="Decrease quantity">
              <Minus size={12} />
            </button>
            <span className="w-6 text-center text-sm" aria-label="Quantity">{quantity}</span>
            <button onClick={() => cart.setQuantity(product.id, quantity + 1)} className="p-1.5" aria-label="Increase quantity">
              <Plus size={12} />
            </button>
          </div>
          <span className="text-sm font-semibold">{formatPrice(product.price == null ? null : product.price * quantity)}</span>
        </div>
      </div>
      <button onClick={() => cart.remove(product.id)} className="self-start p-1 text-ink-muted hover:text-accent" aria-label="Remove">
        <Trash2 size={15} />
      </button>
    </li>
  );
}

export function CartDrawer() {
  const cart = useCart();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && cart.setOpen(false);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [cart]);

  if (!cart.open) return null;
  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="Your bag">
      <div className="absolute inset-0 bg-ink/40 backdrop-blur-sm" onClick={() => cart.setOpen(false)} />
      <aside className="absolute right-0 top-0 flex h-full w-[min(100vw,420px)] animate-slide-in flex-col bg-canvas shadow-lift">
        <div className="flex items-center justify-between border-b border-mist px-5 py-4">
          <h2 className="text-xl">Your bag <span className="font-sans text-sm text-ink-muted">({cart.count})</span></h2>
          <button onClick={() => cart.setOpen(false)} className="rounded-full p-2 hover:bg-mist" aria-label="Close bag">
            <X size={18} />
          </button>
        </div>
        {cart.lines.length === 0 ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center text-sm text-ink-muted">
            <ShoppingBag size={32} className="text-brand" />
            Your bag is empty.
            <Link to="/products" onClick={() => cart.setOpen(false)} className="btn-primary">Start shopping</Link>
          </div>
        ) : (
          <>
            <ul className="flex-1 divide-y divide-mist overflow-y-auto px-5">
              {cart.lines.map((l) => <CartLineRow key={l.product.id} line={l} />)}
            </ul>
            <div className="border-t border-mist bg-white px-5 py-4">
              <div className="flex justify-between text-sm">
                <span>Subtotal</span>
                <span className="font-semibold">{formatPrice(cart.subtotal)}</span>
              </div>
              <p className="mt-1 text-xs text-ink-muted">Items without a listed price are not included.</p>
              <Link to="/cart" onClick={() => cart.setOpen(false)} className="btn-primary mt-3 w-full">View bag</Link>
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
