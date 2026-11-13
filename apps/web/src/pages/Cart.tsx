import { ShieldCheck, ShoppingBag } from "lucide-react";
import { Link } from "react-router-dom";
import { CartLineRow } from "@/components/CartDrawer";
import { EmptyState } from "@/components/Rail";
import { formatPrice } from "@/lib/api";
import { useCart } from "@/state/cart";
import { useToast } from "@/state/toast";

export default function Cart() {
  const cart = useCart();
  const { notify } = useToast();

  if (cart.lines.length === 0)
    return (
      <EmptyState icon={<ShoppingBag size={24} />} title="Your bag is empty">
        <Link to="/products" className="font-medium text-brand-dark underline">Discover the collection</Link>
      </EmptyState>
    );

  const unpriced = cart.lines.filter((l) => l.product.price == null).length;

  return (
    <div>
      <p className="eyebrow">Checkout</p>
      <h1 className="mt-1 text-4xl">Your bag</h1>
      <div className="mt-8 grid gap-8 lg:grid-cols-[1fr_360px]">
        <ul className="divide-y divide-mist rounded-3xl bg-surface px-6 shadow-card">
          {cart.lines.map((l) => <CartLineRow key={l.product.id} line={l} />)}
        </ul>
        <aside className="h-fit rounded-3xl bg-surface p-6 shadow-card lg:sticky lg:top-36">
          <h2 className="text-xl">Order summary</h2>
          <dl className="mt-4 space-y-2 text-sm">
            <div className="flex justify-between"><dt>Items</dt><dd>{cart.count}</dd></div>
            <div className="flex justify-between"><dt>Subtotal</dt><dd>{formatPrice(cart.subtotal)}</dd></div>
            <div className="flex justify-between text-ink-muted"><dt>Shipping</dt><dd>Free</dd></div>
          </dl>
          <div className="mt-4 flex justify-between border-t border-mist pt-4 font-display text-xl">
            <span>Total</span>
            <span>{formatPrice(cart.subtotal)}</span>
          </div>
          {unpriced > 0 && (
            <p className="mt-2 text-xs text-ink-muted">{unpriced} item(s) have no listed price and are not included.</p>
          )}
          <button
            onClick={() => {
              cart.clear();
              notify("Demo checkout complete: no payment was taken.", "info");
            }}
            className="btn-primary mt-6 w-full py-3"
          >
            Place demo order
          </button>
          <p className="mt-3 inline-flex items-center gap-1.5 text-xs text-ink-muted">
            <ShieldCheck size={13} /> This is a portfolio demo. No real orders or payments.
          </p>
        </aside>
      </div>
    </div>
  );
}
